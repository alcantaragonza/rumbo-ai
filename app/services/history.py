from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation


def list_conversations(
    session: Session,
    *,
    user_id: int | None = None,
    service_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.service),
        )
        .order_by(Conversation.created_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(Conversation.user_id == user_id)
    if service_id is not None:
        stmt = stmt.where(Conversation.service_id == service_id)
    if date_from is not None:
        stmt = stmt.where(Conversation.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Conversation.created_at <= date_to)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).unique())


def get_conversation(session: Session, conversation_id: int) -> Conversation | None:
    return session.scalar(
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.service),
        )
        .where(Conversation.id == conversation_id)
    )
