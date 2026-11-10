import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiToken, User

API_TOKEN_PREFIX = "rumbo_"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_api_token(
    session: Session, user: User, name: str, scope: str
) -> tuple[ApiToken, str]:
    """Crea un token y devuelve el registro junto con el valor en claro."""
    raw_token = f"{API_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    record = ApiToken(
        user_id=user.id,
        name=name,
        token_hash=_hash_token(raw_token),
        scope=scope,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record, raw_token


def authenticate_api_token(
    session: Session, token: str
) -> tuple[User, str] | None:
    """Devuelve el usuario y el alcance si el token es válido."""
    if not token.startswith(API_TOKEN_PREFIX):
        return None

    record = session.scalar(
        select(ApiToken).where(ApiToken.token_hash == _hash_token(token))
    )
    if record is None or record.revoked_at is not None:
        return None

    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        return None

    record.last_used_at = datetime.now(UTC)
    session.commit()
    return user, record.scope


def list_api_tokens(session: Session, user_id: int) -> list[ApiToken]:
    return list(
        session.scalars(
            select(ApiToken)
            .where(ApiToken.user_id == user_id)
            .order_by(ApiToken.created_at.desc())
        ).all()
    )


def revoke_api_token(
    session: Session, token_id: int, *, user_id: int, is_admin: bool
) -> bool:
    record = session.get(ApiToken, token_id)
    if record is None:
        return False
    if not is_admin and record.user_id != user_id:
        return False
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        session.commit()
    return True
