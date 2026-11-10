from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import Activity, Destination
from app.services.catalog import search_destinations


def make_destination(
    session: Session,
    *,
    name: str,
    description: str,
    region: str,
    country: str = "Guatemala",
    interests: list[str],
    season: str | None,
    is_active: bool = True,
) -> Destination:
    destination = Destination(
        name=name,
        description=description,
        region=region,
        country=country,
        interests=interests,
        season=season,
        is_active=is_active,
    )
    session.add(destination)
    session.commit()
    session.refresh(destination)
    return destination


def make_activity(
    session: Session,
    destination: Destination,
    *,
    name: str,
    cost: str,
    is_active: bool = True,
) -> Activity:
    activity = Activity(
        destination_id=destination.id,
        name=name,
        description=f"Actividad {name}",
        category="cultura",
        estimated_cost=Decimal(cost),
        is_active=is_active,
    )
    session.add(activity)
    session.commit()
    return activity


@pytest.fixture
def catalog(db_session: Session) -> Iterator[dict[str, Destination]]:
    antigua = make_destination(
        db_session,
        name="Antigua Guatemala",
        description="Ciudad colonial con iglesias y cafés.",
        region="Sacatepéquez",
        interests=["cultura", "historia", "gastronomia"],
        season="todo el año",
    )
    make_activity(db_session, antigua, name="Caminata", cost="10.00")
    make_activity(db_session, antigua, name="Tour de café", cost="40.00")
    make_activity(db_session, antigua, name="Actividad oculta", cost="5.00", is_active=False)

    atitlan = make_destination(
        db_session,
        name="Lago de Atitlán",
        description="Lago volcánico rodeado de pueblos mayas.",
        region="Sololá",
        interests=["naturaleza", "aventura", "fotografia"],
        season="noviembre a abril",
    )
    make_activity(db_session, atitlan, name="Kayak", cost="20.00")
    make_activity(db_session, atitlan, name="Mirador", cost="60.00")

    inactive = make_destination(
        db_session,
        name="Destino inactivo",
        description="No debe aparecer en búsquedas.",
        region="Petén",
        interests=["cultura"],
        season="todo el año",
        is_active=False,
    )
    make_activity(db_session, inactive, name="Museo", cost="5.00")

    return {"antigua": antigua, "atitlan": atitlan, "inactive": inactive}


def names(results: list[Destination]) -> list[str]:
    return [destination.name for destination in results]


def test_filter_by_interest(db_session: Session, catalog: dict[str, Destination]) -> None:
    results = search_destinations(db_session, interests=["cultura"])

    assert names(results) == ["Antigua Guatemala"]


def test_filter_by_location(db_session: Session, catalog: dict[str, Destination]) -> None:
    results = search_destinations(db_session, location="Sololá")

    assert names(results) == ["Lago de Atitlán"]


def test_filter_by_max_cost_ignores_inactive_activities(
    db_session: Session, catalog: dict[str, Destination]
) -> None:
    results = search_destinations(db_session, max_cost=25)

    assert names(results) == ["Antigua Guatemala", "Lago de Atitlán"]
    assert "Destino inactivo" not in names(results)


def test_filter_by_cost_without_active_matches(
    db_session: Session, catalog: dict[str, Destination]
) -> None:
    assert search_destinations(db_session, max_cost=5) == []


def test_filter_by_season(db_session: Session, catalog: dict[str, Destination]) -> None:
    results = search_destinations(db_session, season="noviembre")

    assert names(results) == ["Lago de Atitlán"]


def test_filter_by_text(db_session: Session, catalog: dict[str, Destination]) -> None:
    results = search_destinations(db_session, q="volcánico")

    assert names(results) == ["Lago de Atitlán"]


def test_inactive_destinations_excluded_by_default(
    db_session: Session, catalog: dict[str, Destination]
) -> None:
    names_active = names(search_destinations(db_session))
    names_all = names(search_destinations(db_session, include_inactive=True))

    assert "Destino inactivo" not in names_active
    assert "Destino inactivo" in names_all


def test_no_matches_returns_empty_list(
    db_session: Session, catalog: dict[str, Destination]
) -> None:
    assert search_destinations(db_session, q="playa inexistente") == []
