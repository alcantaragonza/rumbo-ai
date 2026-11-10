from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import Activity, Destination, User
from app.schemas.catalog import (
    ActivityCreate,
    ActivityRead,
    ActivityUpdate,
    DestinationCreate,
    DestinationRead,
    DestinationUpdate,
)
from app.services.catalog import (
    get_activity,
    get_destination,
    search_activities,
    search_destinations,
)

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


def _ensure_admin_for_inactive(current_user: User, include_inactive: bool) -> None:
    if include_inactive and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede ver registros inactivos",
        )


@router.get("/destinations", response_model=list[DestinationRead], tags=["catálogo"])
def list_destinations(
    db: DbSession,
    current_user: CurrentUser,
    interests: Annotated[list[str] | None, Query()] = None,
    location: str | None = None,
    min_cost: Annotated[float | None, Query(ge=0)] = None,
    max_cost: Annotated[float | None, Query(ge=0)] = None,
    season: str | None = None,
    q: str | None = None,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Destination]:
    _ensure_admin_for_inactive(current_user, include_inactive)
    return search_destinations(
        db,
        interests=interests,
        location=location,
        min_cost=min_cost,
        max_cost=max_cost,
        season=season,
        q=q,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/destinations/{destination_id}", response_model=DestinationRead, tags=["catálogo"]
)
def read_destination(
    destination_id: int,
    db: DbSession,
    current_user: CurrentUser,
    include_inactive: bool = False,
) -> Destination:
    _ensure_admin_for_inactive(current_user, include_inactive)
    destination = get_destination(db, destination_id, include_inactive=include_inactive)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destino no encontrado")
    return destination


@router.post(
    "/destinations",
    response_model=DestinationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["catálogo"],
)
def create_destination(
    payload: DestinationCreate, db: DbSession, _: AdminUser
) -> Destination:
    destination = Destination(**payload.model_dump())
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return destination


@router.patch(
    "/destinations/{destination_id}",
    response_model=DestinationRead,
    tags=["catálogo"],
)
def update_destination(
    destination_id: int,
    payload: DestinationUpdate,
    db: DbSession,
    _: AdminUser,
) -> Destination:
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destino no encontrado")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(destination, field, value)
    db.commit()
    db.refresh(destination)
    return destination


@router.delete(
    "/destinations/{destination_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["catálogo"],
)
def delete_destination(destination_id: int, db: DbSession, _: AdminUser) -> Response:
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destino no encontrado")
    destination.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/activities", response_model=list[ActivityRead], tags=["catálogo"])
def list_activities(
    db: DbSession,
    current_user: CurrentUser,
    destination_id: int | None = None,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Activity]:
    _ensure_admin_for_inactive(current_user, include_inactive)
    return search_activities(
        db,
        destination_id=destination_id,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/activities/{activity_id}", response_model=ActivityRead, tags=["catálogo"]
)
def read_activity(
    activity_id: int,
    db: DbSession,
    current_user: CurrentUser,
    include_inactive: bool = False,
) -> Activity:
    _ensure_admin_for_inactive(current_user, include_inactive)
    activity = get_activity(db, activity_id, include_inactive=include_inactive)
    if activity is None:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return activity


@router.post(
    "/activities",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    tags=["catálogo"],
)
def create_activity(payload: ActivityCreate, db: DbSession, _: AdminUser) -> Activity:
    destination = db.get(Destination, payload.destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destino no encontrado")
    if not destination.is_active:
        raise HTTPException(
            status_code=422, detail="No se puede agregar actividades a un destino inactivo"
        )
    activity = Activity(**payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.patch("/activities/{activity_id}", response_model=ActivityRead, tags=["catálogo"])
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: DbSession,
    _: AdminUser,
) -> Activity:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    data = payload.model_dump(exclude_none=True)
    if "destination_id" in data:
        destination = db.get(Destination, data["destination_id"])
        if destination is None:
            raise HTTPException(status_code=404, detail="Destino no encontrado")
        if not destination.is_active:
            raise HTTPException(
                status_code=422, detail="El destino de destino está inactivo"
            )
    for field, value in data.items():
        setattr(activity, field, value)
    db.commit()
    db.refresh(activity)
    return activity


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["catálogo"],
)
def delete_activity(activity_id: int, db: DbSession, _: AdminUser) -> Response:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    activity.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
