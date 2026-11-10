from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import UserRead
from app.schemas.users import UserCreate, UserUpdate

router = APIRouter(prefix="/users", tags=["usuarios"])

DbSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[UserRead])
def list_users(
    db: DbSession,
    _: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    return list(
        db.scalars(
            select(User).order_by(User.email).limit(limit).offset(offset)
        ).all()
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, _: AdminUser) -> User:
    email = payload.email.strip().lower()
    exists = db.scalar(select(User).where(func.lower(User.email) == email))
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        token_limit=payload.token_limit,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def read_user(user_id: int, db: DbSession, _: AdminUser) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, payload: UserUpdate, db: DbSession, current_admin: AdminUser
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    data = payload.model_dump(exclude_none=True)
    if data.get("is_active") is False and user.id == current_admin.id:
        raise HTTPException(
            status_code=400, detail="No puedes desactivar tu propia cuenta"
        )

    password = data.pop("password", None)
    if password is not None:
        user.password_hash = hash_password(password)

    for field, value in data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(user_id: int, db: DbSession, current_admin: AdminUser) -> Response:
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=400, detail="No puedes desactivar tu propia cuenta"
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
