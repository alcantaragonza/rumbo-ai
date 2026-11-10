from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import AiRequest, AiService, User


class QuotaExceeded(Exception):
    """El usuario no tiene tokens suficientes para la solicitud."""

    status_code = 429
    code = "quota_exceeded"

    def __init__(self, *, used: int, limit: int, required: int) -> None:
        self.used = used
        self.limit = limit
        self.required = required
        super().__init__(
            f"Cuota agotada: usados {used} de {limit} tokens; "
            f"se requieren {required}."
        )


@dataclass(slots=True)
class AiCallResult:
    tokens_in: int
    tokens_out: int
    estimated: bool = False
    content: str = ""

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass(slots=True)
class ServiceUsage:
    service_id: int
    service_slug: str
    service_name: str
    requests: int
    blocked: int
    tokens_in: int
    tokens_out: int

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass(slots=True)
class UsageSummary:
    requests: int
    blocked: int
    tokens_in: int
    tokens_out: int
    by_service: list[ServiceUsage]

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


def estimate_tokens(text: str) -> int:
    """Estimación conservadora cuando el proveedor no informa el uso."""
    return max(1, len(text) // 4)


def get_user_tokens_used(session: Session, user_id: int) -> int:
    total = session.scalar(
        select(
            func.coalesce(
                func.sum(AiRequest.tokens_in + AiRequest.tokens_out), 0
            )
        ).where(
            AiRequest.user_id == user_id,
            AiRequest.status.in_(("ok", "error")),
        )
    )
    return int(total or 0)


def record_ai_request(
    session: Session,
    *,
    user_id: int,
    service_id: int,
    status: str,
    conversation_id: int | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    error_code: str | None = None,
    estimated: bool = False,
    meta: dict[str, object] | None = None,
) -> AiRequest:
    record_meta = dict(meta or {})
    if estimated:
        record_meta["estimated"] = True

    record = AiRequest(
        user_id=user_id,
        service_id=service_id,
        conversation_id=conversation_id,
        status=status,
        error_code=error_code,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        meta=record_meta,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def record_blocked_request(
    session: Session,
    *,
    user: User,
    service_id: int,
    required_tokens: int,
    conversation_id: int | None = None,
) -> AiRequest:
    return record_ai_request(
        session,
        user_id=user.id,
        service_id=service_id,
        conversation_id=conversation_id,
        status="blocked",
        error_code="quota_exceeded",
        meta={
            "used_tokens": get_user_tokens_used(session, user.id),
            "token_limit": user.token_limit,
            "required_tokens": required_tokens,
        },
    )


def enforce_quota(
    session: Session,
    user: User,
    *,
    service_id: int,
    estimated_tokens: int,
    conversation_id: int | None = None,
) -> int:
    """Comprueba la cuota; registra el bloqueo y lanza si no alcanza."""
    used = get_user_tokens_used(session, user.id)
    if used + estimated_tokens > user.token_limit:
        record_blocked_request(
            session,
            user=user,
            service_id=service_id,
            required_tokens=estimated_tokens,
            conversation_id=conversation_id,
        )
        raise QuotaExceeded(
            used=used, limit=user.token_limit, required=estimated_tokens
        )
    return used


def run_ai_call(
    session: Session,
    *,
    user: User,
    service: AiService,
    estimated_tokens: int,
    call: Callable[[], AiCallResult],
    conversation_id: int | None = None,
) -> tuple[AiRequest, AiCallResult]:
    """Ejecuta una llamada al LLM solo si la cuota alcanza."""
    enforce_quota(
        session,
        user,
        service_id=service.id,
        estimated_tokens=estimated_tokens,
        conversation_id=conversation_id,
    )

    started = perf_counter()
    try:
        result = call()
    except Exception:
        latency_ms = int((perf_counter() - started) * 1000)
        record_ai_request(
            session,
            user_id=user.id,
            service_id=service.id,
            conversation_id=conversation_id,
            status="error",
            error_code="provider_error",
            latency_ms=latency_ms,
        )
        raise

    latency_ms = int((perf_counter() - started) * 1000)
    record = record_ai_request(
        session,
        user_id=user.id,
        service_id=service.id,
        conversation_id=conversation_id,
        status="ok",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=latency_ms,
        estimated=result.estimated,
    )
    return record, result


def usage_summary(
    session: Session,
    *,
    user_id: int | None = None,
    service_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> UsageSummary:
    conditions = []
    if user_id is not None:
        conditions.append(AiRequest.user_id == user_id)
    if service_id is not None:
        conditions.append(AiRequest.service_id == service_id)
    if date_from is not None:
        conditions.append(AiRequest.created_at >= date_from)
    if date_to is not None:
        conditions.append(AiRequest.created_at <= date_to)

    consumed = AiRequest.status.in_(("ok", "error"))
    stmt = (
        select(
            AiService.id.label("service_id"),
            AiService.slug.label("service_slug"),
            AiService.name.label("service_name"),
            func.count(AiRequest.id).label("requests"),
            func.coalesce(
                func.sum(case((AiRequest.status == "blocked", 1), else_=0)), 0
            ).label("blocked"),
            func.coalesce(
                func.sum(case((consumed, AiRequest.tokens_in), else_=0)), 0
            ).label("tokens_in"),
            func.coalesce(
                func.sum(case((consumed, AiRequest.tokens_out), else_=0)), 0
            ).label("tokens_out"),
        )
        .join(AiService, AiService.id == AiRequest.service_id)
        .group_by(AiService.id, AiService.slug, AiService.name)
        .order_by(AiService.name)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    rows = session.execute(stmt).all()
    by_service = [
        ServiceUsage(
            service_id=row.service_id,
            service_slug=row.service_slug,
            service_name=row.service_name,
            requests=int(row.requests),
            blocked=int(row.blocked),
            tokens_in=int(row.tokens_in),
            tokens_out=int(row.tokens_out),
        )
        for row in rows
    ]
    return UsageSummary(
        requests=sum(item.requests for item in by_service),
        blocked=sum(item.blocked for item in by_service),
        tokens_in=sum(item.tokens_in for item in by_service),
        tokens_out=sum(item.tokens_out for item in by_service),
        by_service=by_service,
    )
