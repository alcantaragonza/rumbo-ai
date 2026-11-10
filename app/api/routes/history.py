from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, resolve_user_scope
from app.db.session import get_db
from app.models import User
from app.schemas.history import (
    ConversationRead,
    ConversationSummary,
    MessageRead,
)
from app.services.history import get_conversation, list_conversations

router = APIRouter(prefix="/history", tags=["historial"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/conversations", response_model=list[ConversationSummary])
def list_history(
    db: DbSession,
    current_user: CurrentUser,
    user_id: int | None = None,
    service_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConversationSummary]:
    resolved_user_id = resolve_user_scope(current_user, user_id)
    conversations = list_conversations(
        db,
        user_id=resolved_user_id,
        service_id=service_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [
        ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            service_id=conversation.service_id,
            service_slug=conversation.service.slug,
            service_name=conversation.service.name,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=len(conversation.messages),
            tokens_total=sum(
                message.tokens_in + message.tokens_out
                for message in conversation.messages
            ),
        )
        for conversation in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
def read_history(
    conversation_id: int, db: DbSession, current_user: CurrentUser
) -> ConversationRead:
    conversation = get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if current_user.role != "admin" and conversation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    return ConversationRead(
        id=conversation.id,
        title=conversation.title,
        service_id=conversation.service_id,
        service_slug=conversation.service.slug,
        service_name=conversation.service.name,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        tokens_total=sum(
            message.tokens_in + message.tokens_out
            for message in conversation.messages
        ),
        messages=[
            MessageRead.model_validate(message) for message in conversation.messages
        ],
    )
