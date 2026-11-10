from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.chat import answer_chat
from app.ai.llm import LLMClient, get_llm_client
from app.api.deps import get_current_user
from app.api.rate_limit import rate_limit
from app.db.session import get_db
from app.models import AiService, Conversation, User
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/chat", tags=["chat"], dependencies=[Depends(rate_limit)]
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
LLM = Annotated[LLMClient, Depends(get_llm_client)]


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
    llm: LLM,
) -> ChatResponse:
    service = db.scalar(
        select(AiService).where(
            AiService.slug == payload.service_slug,
            AiService.is_enabled.is_(True),
        )
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Servicio de IA no encontrado")

    if payload.conversation_id is not None:
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        if conversation.service_id != service.id:
            raise HTTPException(
                status_code=422,
                detail="La conversación pertenece a otro servicio",
            )
    else:
        title = payload.message.strip()[:80] or "Nueva conversación"
        conversation = Conversation(
            user_id=current_user.id,
            service_id=service.id,
            title=title,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    outcome = answer_chat(
        db,
        user=current_user,
        service=service,
        conversation=conversation,
        message=payload.message,
        llm=llm,
    )
    return ChatResponse(
        conversation_id=outcome.conversation_id,
        message=outcome.content,
        sources=outcome.sources,
        tokens_in=outcome.tokens_in,
        tokens_out=outcome.tokens_out,
        tokens_total=outcome.tokens_total,
        tokens_remaining=outcome.tokens_remaining,
        insufficient_context=outcome.insufficient_context,
    )
