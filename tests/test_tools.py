from sqlalchemy.orm import Session

from app.ai.tools import (
    estimate_cost,
    estimate_distance,
    get_weather,
    search_catalog,
)
from app.models import Activity, Destination


def make_destination(session: Session, *, name: str = "Antigua Guatemala") -> Destination:
    destination = Destination(
        name=name,
        description="Ciudad colonial con iglesias.",
        region="Sacatepéquez",
        country="Guatemala",
        latitude=14.5586,
        longitude=-90.7295,
        interests=["cultura"],
        season="todo el año",
    )
    session.add(destination)
    session.commit()
    session.refresh(destination)
    return destination


def test_estimate_distance() -> None:
    distance = estimate_distance(14.5586, -90.7295, 14.6907, -91.2025)

    assert 45 < distance < 60


def test_estimate_cost() -> None:
    assert estimate_cost([10.0, 20.0], travelers=2) == 60.0


def test_search_catalog_returns_active_destination(db_session: Session) -> None:
    destination = make_destination(db_session)

    results = search_catalog(db_session, interests=["cultura"])

    assert [item.id for item in results] == [destination.id]


def test_weather_uses_cache(db_session: Session) -> None:
    calls = {"count": 0}

    def fetcher(latitude: float, longitude: float, days: int) -> dict[str, object]:
        calls["count"] += 1
        return {"daily": {"time": ["2026-11-10"], "temperature_2m_max": [24]}}

    first = get_weather(db_session, 14.5586, -90.7295, days=1, fetcher=fetcher)
    second = get_weather(db_session, 14.5586, -90.7295, days=1, fetcher=fetcher)

    assert first["available"] is True
    assert first["cached"] is False
    assert second["cached"] is True
    assert calls["count"] == 1


def test_weather_degrades_when_source_fails(db_session: Session) -> None:
    def fetcher(latitude: float, longitude: float, days: int) -> dict[str, object]:
        raise RuntimeError("servicio caído")

    result = get_weather(db_session, 14.5586, -90.7295, days=1, fetcher=fetcher)

    assert result["available"] is False
    assert "servicio caído" in result["error"]


def test_activity_costs_are_summed() -> None:
    activity = Activity(
        destination_id=1,
        name="Prueba",
        description="Prueba",
        category="cultura",
        estimated_cost=12.5,
    )

    assert estimate_cost([float(activity.estimated_cost)]) == 12.5
