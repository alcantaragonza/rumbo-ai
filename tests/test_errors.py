from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.errors import register_exception_handlers
from app.models import AiService, User

DESTINATION_PAYLOAD = {
    "name": "Destino de prueba",
    "description": "Prueba de errores.",
    "region": "Prueba",
    "country": "Guatemala",
    "interests": ["prueba"],
    "season": "todo el año",
}


def test_401_error_shape(client) -> None:
    response = client.get("/api/v1/destinations")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.json()["details"] is None


def test_403_error_shape(as_user) -> None:
    response = as_user.post("/api/v1/destinations", json=DESTINATION_PAYLOAD)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_404_error_shape(as_admin) -> None:
    response = as_admin.get("/api/v1/destinations/99999")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_422_error_shape(as_admin) -> None:
    response = as_admin.post("/api/v1/destinations", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["details"], list)
    assert body["details"]


def test_quota_error_shape(
    as_user, regular_user: User, db_session: Session
) -> None:
    service = AiService(slug="chatbot", name="Chatbot", kind="chatbot")
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    regular_user.token_limit = 0
    db_session.commit()

    response = as_user.post(
        "/api/v1/ai/quota-check",
        json={"service_id": service.id, "estimated_tokens": 1},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "quota_exceeded"


def test_rate_limit_error_shape(
    as_user, db_session: Session, monkeypatch
) -> None:
    service = AiService(slug="chatbot", name="Chatbot", kind="chatbot")
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    monkeypatch.setattr("app.api.rate_limit.MAX_REQUESTS", 1)

    first = as_user.post(
        "/api/v1/ai/quota-check",
        json={"service_id": service.id, "estimated_tokens": 1},
    )
    second = as_user.post(
        "/api/v1/ai/quota-check",
        json={"service_id": service.id, "estimated_tokens": 1},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limited"


def test_500_error_shape() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    def boom() -> None:
        raise RuntimeError("boom")

    test_app.add_api_route("/boom", boom, methods=["GET"])

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
