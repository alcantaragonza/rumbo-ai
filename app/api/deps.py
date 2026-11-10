from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.services.auth import SESSION_COOKIE, get_user_for_token
from app.services.tokens import API_TOKEN_PREFIX, authenticate_api_token

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    cookie_token = request.cookies.get(SESSION_COOKIE)
    if cookie_token:
        user = get_user_for_token(db, cookie_token)
        if user is not None:
            request.state.auth_scope = "write"
            return user

    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token.startswith(API_TOKEN_PREFIX):
            authenticated = authenticate_api_token(db, token)
            if authenticated is not None:
                user, scope = authenticated
                request.state.auth_scope = scope
                return user
        else:
            user = get_user_for_token(db, token)
            if user is not None:
                request.state.auth_scope = "write"
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere autenticación",
    )


def require_write(request: Request, user: Annotated[User, Depends(get_current_user)]) -> User:
    if getattr(request.state, "auth_scope", "write") != "write":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token de API es de solo lectura",
        )
    return user


def resolve_user_scope(current_user: User, user_id: int | None) -> int | None:
    """Limita a un usuario normal a sus propios datos."""
    if current_user.role == "admin":
        return user_id
    if user_id is not None and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes consultar datos de otro usuario",
        )
    return current_user.id


def require_admin(
    request: Request, user: Annotated[User, Depends(get_current_user)]
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere el rol admin",
        )
    if getattr(request.state, "auth_scope", "write") != "write":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token de API es de solo lectura",
        )
    return user
