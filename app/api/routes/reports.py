from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, resolve_user_scope
from app.db.session import get_db
from app.models import User
from app.schemas.reports import UsageReportResponse
from app.services.reports import usage_report

router = APIRouter(prefix="/reports", tags=["reportes"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/usage", response_model=UsageReportResponse)
def get_usage_report(
    db: DbSession,
    current_user: CurrentUser,
    user_id: int | None = None,
    service_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> UsageReportResponse:
    resolved_user_id = resolve_user_scope(current_user, user_id)
    if resolved_user_id is not None and db.get(User, resolved_user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usage_report(
        db,
        user_id=resolved_user_id,
        service_id=service_id,
        date_from=date_from,
        date_to=date_to,
    )
