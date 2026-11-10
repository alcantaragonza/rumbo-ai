from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.rate_limit import rate_limit
from app.db.session import get_db
from app.models import AiService, User
from app.schemas.usage import QuotaCheckRequest, QuotaCheckResponse
from app.services.usage import enforce_quota, get_user_tokens_used

router = APIRouter(
    prefix="/ai", tags=["IA"], dependencies=[Depends(rate_limit)]
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/quota-check", response_model=QuotaCheckResponse)
def quota_check(
    payload: QuotaCheckRequest, db: DbSession, current_user: CurrentUser
) -> QuotaCheckResponse:
    service = db.get(AiService, payload.service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    if not service.is_enabled:
        raise HTTPException(status_code=422, detail="El servicio está desactivado")

    enforce_quota(
        db,
        current_user,
        service_id=service.id,
        estimated_tokens=payload.estimated_tokens,
    )
    used = get_user_tokens_used(db, current_user.id)
    return QuotaCheckResponse(
        ok=True,
        tokens_used=used,
        token_limit=current_user.token_limit,
        tokens_remaining=max(current_user.token_limit - used, 0),
    )
