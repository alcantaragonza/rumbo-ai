import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import HashEmbeddingClient
from app.ai.llm import FakeLLMClient
from app.api.routes.chat import get_llm_client
from app.main import app
from app.models import Activity, AiRequest, AiService, Conversation, Destination, User

embedder = HashEmbeddingClient()


def make_service(session: Session) -> AiService:
    service = AiService(slug="chatbot", name="Chatbot", kind="chatbot")
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def make_catalog(session: Session) -> tuple[Destination, Activity]:
    destination_text = (
        "Antigua Guatemala ciudad colonial cultura historia gastronomia "
        "Sacatepéquez Guatemala todo el año"
    )
    destination = Destination(
        name="Antigua Guatemala",
        description="Ciudad colonial con iglesias y cafés.",
        region="Sacatepéquez",
        country="Guatemala",
        interests=["cultura", "historia", "gastronomia"],
        season="todo el año",
        embedding=embedder.embed([destination_text])[0],
    )
    session.add(destination)
    session.flush()

    activity_text = "Caminata por el centro histórico cultura Antigua Guatemala"
    activity = Activity(
        destination_id=destination.id,
        name="Caminata por el centro histórico",
        description="Recorrido guiado por el parque central.",
        category="cultura",
        estimated_cost=15,
        duration_minutes=120,
        embedding=embedder.embed([activity_text])[0],
    )
    session.add(activity)
    session.commit()
    session.refresh(destination)
    session.refresh(activity)
    return destination, activity


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    client = FakeLLMClient("RESPUESTA_UNICA_123: visita el centro histórico.")
    app.dependency_overrides[get_llm_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_llm_client, None)


def test_chat_returns_sources_and_persists(
    as_user, fake_llm: FakeLLMClient, db_session: Session
) -> None:
    make_service(db_session)
    make_catalog(db_session)

    response = as_user.post(
        "/api/v1/chat", json={"message": "Quiero visitar Antigua Guatemala"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["insufficient_context"] is False
    assert data["sources"]
    assert "RESPUESTA_UNICA_123" in data["message"]

    conversation = db_session.get(Conversation, data["conversation_id"])
    assert conversation is not None
    assert len(conversation.messages) == 2
    assert conversation.messages[1].sources

    detail = as_user.get(
        f"/api/v1/history/conversations/{data['conversation_id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["messages"][1]["sources"]

    usage = as_user.get("/api/v1/usage")
    assert usage.status_code == 200
    assert usage.json()["tokens_total"] > 0


def test_follow_up_uses_conversation_memory(
    as_user, fake_llm: FakeLLMClient, db_session: Session
) -> None:
    make_service(db_session)
    make_catalog(db_session)

    first = as_user.post(
        "/api/v1/chat", json={"message": "Quiero visitar Antigua Guatemala"}
    )
    conversation_id = first.json()["conversation_id"]

    fake_llm.calls.clear()
    second = as_user.post(
        "/api/v1/chat",
        json={
            "message": "¿y qué actividades hay para dos días?",
            "conversation_id": conversation_id,
        },
    )

    assert second.status_code == 200
    prompt = " ".join(
        message["content"] for message in fake_llm.calls[-1]
    )
    assert "RESPUESTA_UNICA_123" in prompt


def test_new_conversation_does_not_inherit_memory(
    as_user, fake_llm: FakeLLMClient, db_session: Session
) -> None:
    make_service(db_session)
    make_catalog(db_session)

    as_user.post(
        "/api/v1/chat", json={"message": "Quiero visitar Antigua Guatemala"}
    )

    fake_llm.calls.clear()
    response = as_user.post(
        "/api/v1/chat", json={"message": "Quiero visitar Antigua Guatemala otra vez"}
    )

    assert response.status_code == 200
    prompt = " ".join(
        message["content"] for message in fake_llm.calls[-1]
    )
    assert "RESPUESTA_UNICA_123" not in prompt


def test_insufficient_context_does_not_call_llm(
    as_user, fake_llm: FakeLLMClient, db_session: Session
) -> None:
    make_service(db_session)
    make_catalog(db_session)
    fake_llm.calls.clear()

    response = as_user.post(
        "/api/v1/chat", json={"message": "Quiero viajar a la playa de Marte"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["insufficient_context"] is True
    assert data["sources"] == []
    assert fake_llm.calls == []


def test_quota_exhausted_blocks_before_llm(
    as_user, fake_llm: FakeLLMClient, db_session: Session, regular_user: User
) -> None:
    make_service(db_session)
    make_catalog(db_session)
    regular_user.token_limit = 0
    db_session.commit()

    response = as_user.post(
        "/api/v1/chat", json={"message": "Quiero visitar Antigua Guatemala"}
    )

    assert response.status_code == 429
    assert fake_llm.calls == []
    blocked = db_session.scalar(
        select(AiRequest).where(AiRequest.status == "blocked")
    )
    assert blocked is not None


def test_chat_requires_authentication(client) -> None:
    response = client.post("/api/v1/chat", json={"message": "Hola"})

    assert response.status_code == 401
