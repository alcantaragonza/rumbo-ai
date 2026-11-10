from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_write
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, UserRead
from app.schemas.tokens import ApiTokenCreate, ApiTokenCreated, ApiTokenRead
from app.services.auth import (
    SESSION_COOKIE,
    create_session,
    revoke_session,
)
from app.services.tokens import create_api_token, list_api_tokens, revoke_api_token

router = APIRouter(prefix="/auth", tags=["autenticación"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentWriter = Annotated[User, Depends(require_write)]


def _cookie_secure() -> bool:
    return get_settings().env not in {"development", "test"}


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: DbSession) -> User:
    user = db.scalar(
        select(User).where(func.lower(User.email) == payload.email.strip().lower())
    )
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    token = create_session(db, user)
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: DbSession) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(db, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> User:
    return current_user


@router.post(
    "/tokens",
    response_model=ApiTokenCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_token(
    payload: ApiTokenCreate, current_user: CurrentWriter, db: DbSession
) -> ApiTokenCreated:
    record, raw_token = create_api_token(
        db, current_user, payload.name, payload.scope
    )
    return ApiTokenCreated(
        **ApiTokenRead.model_validate(record).model_dump(),
        token=raw_token,
    )


@router.get("/tokens", response_model=list[ApiTokenRead])
def get_tokens(current_user: CurrentUser, db: DbSession) -> list[ApiTokenRead]:
    return [
        ApiTokenRead.model_validate(record)
        for record in list_api_tokens(db, current_user.id)
    ]


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_token(
    token_id: int, current_user: CurrentWriter, db: DbSession
) -> Response:
    revoked = revoke_api_token(
        db,
        token_id,
        user_id=current_user.id,
        is_admin=current_user.role == "admin",
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
