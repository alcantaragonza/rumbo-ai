from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models import Activity, Destination


def search_destinations(
    session: Session,
    *,
    interests: list[str] | None = None,
    location: str | None = None,
    min_cost: float | None = None,
    max_cost: float | None = None,
    season: str | None = None,
    q: str | None = None,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Destination]:
    """Busca destinos activos con filtros combinables."""
    stmt = (
        select(Destination)
        .options(selectinload(Destination.activities))
        .order_by(Destination.name)
    )

    if not include_inactive:
        stmt = stmt.where(Destination.is_active.is_(True))

    if interests:
        stmt = stmt.where(Destination.interests.overlap(interests))

    if location:
        pattern = f"%{location.strip()}%"
        stmt = stmt.where(
            or_(
                Destination.region.ilike(pattern),
                Destination.country.ilike(pattern),
                Destination.name.ilike(pattern),
            )
        )

    if season:
        stmt = stmt.where(Destination.season.ilike(f"%{season.strip()}%"))

    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Destination.name.ilike(pattern),
                Destination.description.ilike(pattern),
                Destination.region.ilike(pattern),
                Destination.country.ilike(pattern),
            )
        )

    if min_cost is not None or max_cost is not None:
        cost_filters: list[ColumnElement[bool]] = [Activity.is_active.is_(True)]
        if min_cost is not None:
            cost_filters.append(Activity.estimated_cost >= min_cost)
        if max_cost is not None:
            cost_filters.append(Activity.estimated_cost <= max_cost)
        stmt = stmt.where(
            exists().where(Activity.destination_id == Destination.id, *cost_filters)
        )

    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).unique())


def get_destination(
    session: Session, destination_id: int, *, include_inactive: bool = False
) -> Destination | None:
    stmt = (
        select(Destination)
        .options(selectinload(Destination.activities))
        .where(Destination.id == destination_id)
    )
    if not include_inactive:
        stmt = stmt.where(Destination.is_active.is_(True))
    return session.scalar(stmt)


def search_activities(
    session: Session,
    *,
    destination_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Activity]:
    """Lista actividades; por defecto solo de destinos activos."""
    stmt = select(Activity).order_by(Activity.name)
    if destination_id is not None:
        stmt = stmt.where(Activity.destination_id == destination_id)
    if not include_inactive:
        stmt = stmt.join(Destination).where(
            Activity.is_active.is_(True), Destination.is_active.is_(True)
        )
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


def get_activity(
    session: Session, activity_id: int, *, include_inactive: bool = False
) -> Activity | None:
    stmt = select(Activity).where(Activity.id == activity_id)
    if not include_inactive:
        stmt = stmt.join(Destination).where(
            Activity.is_active.is_(True), Destination.is_active.is_(True)
        )
    return session.scalar(stmt)
