from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AiService, User
from app.schemas.services import ServiceRead

router = APIRouter(prefix="/services", tags=["servicios"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[ServiceRead])
def list_services(
    db: DbSession,
    current_user: CurrentUser,
    include_disabled: bool = False,
) -> list[AiService]:
    if include_disabled and current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Solo el administrador puede ver servicios desactivados"
        )
    stmt = select(AiService).order_by(AiService.name)
    if not include_disabled:
        stmt = stmt.where(AiService.is_enabled.is_(True))
    return list(db.scalars(stmt).all())
