from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExternalCache


def get_cache(session: Session, source: str, key: str) -> dict[str, Any] | None:
    record = session.scalar(
        select(ExternalCache).where(
            ExternalCache.source == source,
            ExternalCache.cache_key == key,
        )
    )
    if record is None or record.expires_at <= datetime.now(UTC):
        return None
    return record.payload


def set_cache(
    session: Session,
    source: str,
    key: str,
    payload: dict[str, Any],
    *,
    ttl_seconds: int,
) -> None:
    record = session.scalar(
        select(ExternalCache).where(
            ExternalCache.source == source,
            ExternalCache.cache_key == key,
        )
    )
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    if record is None:
        session.add(
            ExternalCache(
                source=source,
                cache_key=key,
                payload=payload,
                expires_at=expires_at,
            )
        )
    else:
        record.payload = payload
        record.expires_at = expires_at
    session.commit()
