from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, resolve_user_scope
from app.db.session import get_db
from app.models import User
from app.schemas.usage import ServiceUsageRead, UsageSummaryRead
from app.services.usage import get_user_tokens_used, usage_summary

router = APIRouter(prefix="/usage", tags=["consumo"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=UsageSummaryRead)
def get_usage(
    db: DbSession,
    current_user: CurrentUser,
    user_id: int | None = None,
    service_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> UsageSummaryRead:
    resolved_user_id = resolve_user_scope(current_user, user_id)
    target = None
    if resolved_user_id is not None:
        target = db.get(User, resolved_user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

    summary = usage_summary(
        db,
        user_id=resolved_user_id,
        service_id=service_id,
        date_from=date_from,
        date_to=date_to,
    )
    tokens_used = (
        get_user_tokens_used(db, resolved_user_id)
        if resolved_user_id is not None
        else summary.tokens_total
    )
    token_limit = target.token_limit if target is not None else None
    tokens_remaining = (
        max(token_limit - tokens_used, 0) if token_limit is not None else None
    )

    return UsageSummaryRead(
        user_id=resolved_user_id,
        token_limit=token_limit,
        tokens_used=tokens_used,
        tokens_remaining=tokens_remaining,
        requests=summary.requests,
        blocked=summary.blocked,
        tokens_in=summary.tokens_in,
        tokens_out=summary.tokens_out,
        tokens_total=summary.tokens_total,
        by_service=[
            ServiceUsageRead(
                service_id=item.service_id,
                service_slug=item.service_slug,
                service_name=item.service_name,
                requests=item.requests,
                blocked=item.blocked,
                tokens_in=item.tokens_in,
                tokens_out=item.tokens_out,
                tokens_total=item.tokens_total,
            )
            for item in summary.by_service
        ],
    )
