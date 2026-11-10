import pytest
from sqlalchemy.orm import Session

from app.ai.llm import FakeLLMClient
from app.api.routes.agents import get_llm_client
from app.main import app
from app.models import Activity, AiService, Destination, User


def make_services(session: Session) -> None:
    session.add_all(
        [
            AiService(slug="itinerary-planner", name="Planificador", kind="agent"),
            AiService(slug="trip-adjuster", name="Ajuste", kind="agent"),
        ]
    )
    session.commit()


def make_catalog(session: Session) -> Destination:
    destination = Destination(
        name="Antigua Guatemala",
        description="Ciudad colonial con iglesias y cafés.",
        region="Sacatepéquez",
        country="Guatemala",
        latitude=14.5586,
        longitude=-90.7295,
        interests=["cultura", "historia", "gastronomia"],
        season="todo el año",
    )
    session.add(destination)
    session.flush()
    session.add_all(
        [
            Activity(
                destination_id=destination.id,
                name="Caminata cultural",
                description="Recorrido por iglesias y plazas.",
                category="cultura",
                estimated_cost=15,
                duration_minutes=120,
            ),
            Activity(
                destination_id=destination.id,
                name="Tour gastronómico",
                description="Degustación de café y platos típicos.",
                category="gastronomia",
                estimated_cost=35,
                duration_minutes=180,
            ),
            Activity(
                destination_id=destination.id,
                name="Kayak",
                description="Paseo al aire libre.",
                category="aventura",
                estimated_cost=20,
                duration_minutes=120,
            ),
            Activity(
                destination_id=destination.id,
                name="Mirador",
                description="Caminata al mirador.",
                category="naturaleza",
                estimated_cost=30,
                duration_minutes=150,
            ),
        ]
    )
    session.commit()
    session.refresh(destination)
    return destination


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    client = FakeLLMClient("Resumen del plan.")
    app.dependency_overrides[get_llm_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture
def weather_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def fetcher(latitude: float, longitude: float, days: int) -> dict[str, object]:
        return {
            "daily": {
                "time": ["2026-11-10", "2026-11-11"],
                "temperature_2m_max": [24, 25],
                "temperature_2m_min": [14, 15],
                "precipitation_probability_max": [10, 20],
            }
        }

    monkeypatch.setattr("app.ai.tools._fetch_open_meteo", fetcher)


def test_itinerary_endpoint(
    as_user, fake_llm: FakeLLMClient, weather_ok, db_session: Session
) -> None:
    make_services(db_session)
    destination = make_catalog(db_session)

    response = as_user.post(
        "/api/v1/agents/itinerary",
        json={
            "destination_id": destination.id,
            "days": 2,
            "budget": 200,
            "travelers": 2,
            "origin_latitude": 14.6,
            "origin_longitude": -90.7,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["service_slug"] == "itinerary-planner"
    assert data["destination"]["id"] == destination.id
    assert len(data["itinerary"]) == 2
    assert data["estimated_cost"] > 0
    assert data["sources"]
    assert data["steps"]
    assert data["summary"] == "Resumen del plan."
    assert data["tokens_total"] > 0
    assert data["weather"]["available"] is True
    assert data["distance_km"] is not None
    assert data["within_budget"] is True


def test_itinerary_without_preferences_asks_for_destination(
    as_user, fake_llm: FakeLLMClient, db_session: Session
) -> None:
    make_services(db_session)

    response = as_user.post(
        "/api/v1/agents/itinerary", json={"days": 2}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["missing_info"] == ["destination"]
    assert fake_llm.calls == []


def test_itinerary_degrades_when_weather_fails(
    as_user, fake_llm: FakeLLMClient, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    make_services(db_session)
    destination = make_catalog(db_session)

    def failing_fetcher(
        latitude: float, longitude: float, days: int
    ) -> dict[str, object]:
        raise RuntimeError("clima no disponible")

    monkeypatch.setattr("app.ai.tools._fetch_open_meteo", failing_fetcher)

    response = as_user.post(
        "/api/v1/agents/itinerary",
        json={"destination_id": destination.id, "days": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["weather"]["available"] is False
    assert data["warnings"]
    assert data["itinerary"]


def test_adjust_rain_replaces_outdoor_activities(
    as_user, fake_llm: FakeLLMClient, weather_ok, db_session: Session
) -> None:
    make_services(db_session)
    make_catalog(db_session)

    response = as_user.post(
        "/api/v1/agents/adjust",
        json={
            "destination_query": "Antigua",
            "days": 1,
            "interests": ["aventura", "naturaleza"],
            "change": "rain",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["replaced"]
    categories = {
        activity["category"]
        for day in data["itinerary"]
        for activity in day["activities"]
    }
    assert categories <= {"cultura", "gastronomia"}


def test_adjust_budget_keeps_cost_within_limit(
    as_user, fake_llm: FakeLLMClient, weather_ok, db_session: Session
) -> None:
    make_services(db_session)
    destination = make_catalog(db_session)

    response = as_user.post(
        "/api/v1/agents/adjust",
        json={
            "destination_id": destination.id,
            "days": 2,
            "change": "budget",
            "new_budget": 30,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["within_budget"] is True
    assert data["estimated_cost"] <= 30
    assert data["replaced"]


def test_agent_respects_quota(
    as_user, fake_llm: FakeLLMClient, weather_ok, db_session: Session, regular_user: User
) -> None:
    make_services(db_session)
    destination = make_catalog(db_session)
    regular_user.token_limit = 0
    db_session.commit()

    response = as_user.post(
        "/api/v1/agents/itinerary",
        json={"destination_id": destination.id, "days": 1},
    )

    assert response.status_code == 429
    assert fake_llm.calls == []


def test_agents_require_authentication(client) -> None:
    assert client.post("/api/v1/agents/itinerary", json={"days": 1}).status_code == 401
    assert client.post("/api/v1/agents/adjust", json={"days": 1}).status_code == 401
