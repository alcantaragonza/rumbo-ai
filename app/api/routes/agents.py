from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.agents import AgentRequest, run_adjustment, run_itinerary
from app.ai.llm import LLMClient, get_llm_client
from app.api.deps import get_current_user
from app.api.rate_limit import rate_limit
from app.db.session import get_db
from app.models import AiService, User
from app.schemas.agents import AdjustRequest, AgentResponse, ItineraryRequest

router = APIRouter(
    prefix="/agents", tags=["agentes"], dependencies=[Depends(rate_limit)]
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
LLM = Annotated[LLMClient, Depends(get_llm_client)]


def _get_service(db: Session, slug: str) -> AiService:
    service = db.scalar(
        select(AiService).where(
            AiService.slug == slug,
            AiService.is_enabled.is_(True),
        )
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Servicio de agentes no disponible")
    return service


@router.post("/itinerary", response_model=AgentResponse)
def itinerary(
    payload: ItineraryRequest,
    db: DbSession,
    current_user: CurrentUser,
    llm: LLM,
) -> AgentResponse:
    service = _get_service(db, "itinerary-planner")
    result = run_itinerary(
        db,
        user=current_user,
        service=service,
        llm=llm,
        request=AgentRequest(**payload.model_dump()),
    )
    return AgentResponse(**result.to_dict())


@router.post("/adjust", response_model=AgentResponse)
def adjust(
    payload: AdjustRequest,
    db: DbSession,
    current_user: CurrentUser,
    llm: LLM,
) -> AgentResponse:
    service = _get_service(db, "trip-adjuster")
    result = run_adjustment(
        db,
        user=current_user,
        service=service,
        llm=llm,
        request=AgentRequest(**payload.model_dump()),
    )
    return AgentResponse(**result.to_dict())
