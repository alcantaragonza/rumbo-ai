from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.llm import LLMClient
from app.ai.retrieval import RetrievedItem, format_context, retrieve
from app.models import AiService, Conversation, Message, User
from app.services.usage import (
    enforce_quota,
    estimate_tokens,
    get_user_tokens_used,
    record_ai_request,
    run_ai_call,
)

INSUFFICIENT_MESSAGE = (
    "No encontré información suficiente en el catálogo para responder. "
    "Reformula la pregunta o consulta otro destino."
)

MAX_RECENT_MESSAGES = 10
MAX_SUMMARY_CHARS = 1500


@dataclass(slots=True)
class ChatOutcome:
    conversation_id: int
    content: str
    sources: list[dict[str, object]]
    tokens_in: int
    tokens_out: int
    tokens_remaining: int
    insufficient_context: bool

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


def build_memory(messages: list[Message]) -> list[dict[str, str]]:
    """Ventana de mensajes recientes con resumen de los anteriores."""
    serialized = [
        {"role": message.role, "content": message.content} for message in messages
    ]
    if len(serialized) <= MAX_RECENT_MESSAGES:
        return serialized

    older = serialized[:-MAX_RECENT_MESSAGES]
    recent = serialized[-MAX_RECENT_MESSAGES:]
    summary = "Resumen de la conversación anterior: " + " | ".join(
        f"{item['role']}: {item['content']}" for item in older
    )
    return [{"role": "system", "content": summary[:MAX_SUMMARY_CHARS]}, *recent]


def build_retrieval_query(messages: list[Message], message: str) -> str:
    """Incluye preguntas previas del usuario para resolver seguimientos."""
    previous = [item.content for item in messages if item.role == "user"][-4:]
    return " ".join([*previous, message])[:600]


def build_prompt(
    service: AiService,
    items: list[RetrievedItem],
    memory: list[dict[str, str]],
    message: str,
) -> list[dict[str, str]]:
    system = (
        service.system_prompt
        or "Eres un asistente turístico que responde en español."
    ).strip()
    system += (
        "\nResponde solo con el contexto del catálogo. Si no alcanza, dilo "
        "explícitamente. Cita las fuentes usadas como [n]."
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "system",
            "content": f"Contexto del catálogo:\n{format_context(items)}",
        },
        *memory,
        {"role": "user", "content": message},
    ]


def answer_chat(
    session: Session,
    *,
    user: User,
    service: AiService,
    conversation: Conversation,
    message: str,
    llm: LLMClient,
) -> ChatOutcome:
    history = list(conversation.messages)
    items = retrieve(session, build_retrieval_query(history, message))

    if not items:
        user_message = Message(
            role="user",
            content=message,
            tokens_in=estimate_tokens(message),
        )
        assistant_message = Message(
            role="assistant",
            content=INSUFFICIENT_MESSAGE,
            sources=[],
            tokens_out=estimate_tokens(INSUFFICIENT_MESSAGE),
        )
        conversation.messages.extend([user_message, assistant_message])
        conversation.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(assistant_message)
        record_ai_request(
            session,
            user_id=user.id,
            service_id=service.id,
            conversation_id=conversation.id,
            status="ok",
            meta={"insufficient_context": True},
        )
        used = get_user_tokens_used(session, user.id)
        return ChatOutcome(
            conversation_id=conversation.id,
            content=INSUFFICIENT_MESSAGE,
            sources=[],
            tokens_in=0,
            tokens_out=0,
            tokens_remaining=max(user.token_limit - used, 0),
            insufficient_context=True,
        )

    prompt = build_prompt(service, items, build_memory(history), message)
    estimated_tokens = estimate_tokens(
        " ".join(str(item["content"]) for item in prompt)
    ) + 256

    enforce_quota(
        session,
        user,
        service_id=service.id,
        estimated_tokens=estimated_tokens,
        conversation_id=conversation.id,
    )

    user_message = Message(
        role="user",
        content=message,
        tokens_in=estimate_tokens(message),
    )
    conversation.messages.append(user_message)
    session.flush()

    record, result = run_ai_call(
        session,
        user=user,
        service=service,
        estimated_tokens=estimated_tokens,
        conversation_id=conversation.id,
        call=lambda: llm.complete(
            prompt, model=service.model, max_tokens=512
        ),
    )

    sources = [item.to_source() for item in items]
    assistant_message = Message(
        role="assistant",
        content=result.content,
        sources=sources,
        tokens_in=record.tokens_in,
        tokens_out=record.tokens_out,
    )
    conversation.messages.append(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(assistant_message)

    used = get_user_tokens_used(session, user.id)
    return ChatOutcome(
        conversation_id=conversation.id,
        content=assistant_message.content,
        sources=sources,
        tokens_in=record.tokens_in,
        tokens_out=record.tokens_out,
        tokens_remaining=max(user.token_limit - used, 0),
        insufficient_context=False,
    )
