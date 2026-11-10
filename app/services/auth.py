import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserSession

SESSION_COOKIE = "rumbo_session"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(session: Session, user: User) -> str:
    """Crea una sesión y devuelve el token en claro (solo se guarda su hash)."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    record = UserSession(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.session_ttl_minutes),
    )
    session.add(record)
    session.commit()
    return token


def get_user_for_token(session: Session, token: str) -> User | None:
    record = session.scalar(
        select(UserSession).where(UserSession.token_hash == _hash_token(token))
    )
    if record is None or record.revoked_at is not None:
        return None
    if record.expires_at <= datetime.now(UTC):
        return None
    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(session: Session, token: str) -> None:
    record = session.scalar(
        select(UserSession).where(UserSession.token_hash == _hash_token(token))
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        session.commit()
