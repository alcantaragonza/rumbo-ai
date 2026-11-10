from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AiService, Conversation, Message, User
from app.services.usage import record_ai_request


def make_user(session: Session, email: str) -> User:
    user = User(
        email=email,
        password_hash="not-used",
        full_name=email,
        role="user",
        token_limit=1000,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_service(session: Session, slug: str, name: str) -> AiService:
    service = AiService(slug=slug, name=name, kind="chatbot")
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def make_conversation(
    session: Session,
    *,
    user_id: int,
    service_id: int,
    title: str,
    tokens_in: int,
    tokens_out: int,
) -> Conversation:
    conversation = Conversation(
        user_id=user_id, service_id=service_id, title=title
    )
    session.add(conversation)
    session.flush()
    session.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content="¿Qué puedo visitar?",
            tokens_in=tokens_in,
            tokens_out=0,
        )
    )
    session.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content="Puedes visitar el centro histórico.",
            sources=[{"type": "destination", "id": 1}],
            tokens_in=0,
            tokens_out=tokens_out,
        )
    )
    session.commit()
    session.refresh(conversation)
    return conversation


def test_user_only_sees_own_history(
    as_user, db_session: Session, regular_user: User
) -> None:
    regular_user.token_limit = 1000
    db_session.commit()
    service = make_service(db_session, "chatbot", "Chatbot")
    other = make_user(db_session, "other@rumbo.ai")
    own = make_conversation(
        db_session,
        user_id=1,
        service_id=service.id,
        title="Mi conversación",
        tokens_in=10,
        tokens_out=5,
    )
    foreign = make_conversation(
        db_session,
        user_id=other.id,
        service_id=service.id,
        title="Ajena",
        tokens_in=20,
        tokens_out=10,
    )
    record_ai_request(
        db_session,
        user_id=1,
        service_id=service.id,
        conversation_id=own.id,
        status="ok",
        tokens_in=10,
        tokens_out=5,
    )

    listing = as_user.get("/api/v1/history/conversations")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [own.id]

    detail = as_user.get(f"/api/v1/history/conversations/{own.id}")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 2

    assert (
        as_user.get(f"/api/v1/history/conversations/{foreign.id}").status_code
        == 404
    )

    usage = as_user.get("/api/v1/usage")
    assert usage.status_code == 200
    assert usage.json()["user_id"] == 1
    assert usage.json()["tokens_used"] == 15
    assert usage.json()["tokens_remaining"] == 985

    forbidden = as_user.get("/api/v1/usage", params={"user_id": other.id})
    assert forbidden.status_code == 403


def test_admin_can_see_global_and_filtered_usage(
    as_admin, db_session: Session, admin_user: User
) -> None:
    service = make_service(db_session, "chatbot", "Chatbot")
    other = make_user(db_session, "other@rumbo.ai")
    make_conversation(
        db_session,
        user_id=admin_user.id,
        service_id=service.id,
        title="Admin",
        tokens_in=10,
        tokens_out=5,
    )
    foreign = make_conversation(
        db_session,
        user_id=other.id,
        service_id=service.id,
        title="Otro",
        tokens_in=20,
        tokens_out=10,
    )
    record_ai_request(
        db_session,
        user_id=admin_user.id,
        service_id=service.id,
        status="ok",
        tokens_in=10,
        tokens_out=5,
    )
    record_ai_request(
        db_session,
        user_id=other.id,
        service_id=service.id,
        status="ok",
        tokens_in=20,
        tokens_out=10,
    )

    global_usage = as_admin.get("/api/v1/usage")
    assert global_usage.status_code == 200
    assert global_usage.json()["user_id"] is None
    assert global_usage.json()["tokens_used"] == 45

    filtered = as_admin.get("/api/v1/usage", params={"user_id": other.id})
    assert filtered.status_code == 200
    assert filtered.json()["user_id"] == other.id
    assert filtered.json()["tokens_used"] == 30

    conversation = as_admin.get(f"/api/v1/history/conversations/{foreign.id}")
    assert conversation.status_code == 200


def test_history_filters_by_service(
    as_user, db_session: Session, regular_user: User
) -> None:
    chatbot = make_service(db_session, "chatbot", "Chatbot")
    planner = make_service(db_session, "itinerary-planner", "Planificador")
    make_conversation(
        db_session,
        user_id=1,
        service_id=chatbot.id,
        title="Chat",
        tokens_in=10,
        tokens_out=5,
    )
    planned = make_conversation(
        db_session,
        user_id=1,
        service_id=planner.id,
        title="Itinerario",
        tokens_in=20,
        tokens_out=10,
    )
    record_ai_request(
        db_session,
        user_id=regular_user.id,
        service_id=planner.id,
        status="ok",
        tokens_in=20,
        tokens_out=10,
    )

    listing = as_user.get(
        "/api/v1/history/conversations", params={"service_id": planner.id}
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [planned.id]

    usage = as_user.get("/api/v1/usage", params={"service_id": planner.id})
    assert usage.status_code == 200
    assert len(usage.json()["by_service"]) == 1
    assert usage.json()["by_service"][0]["service_slug"] == "itinerary-planner"


def test_services_endpoint_lists_enabled_services(
    as_user, db_session: Session
) -> None:
    make_service(db_session, "chatbot", "Chatbot")

    response = as_user.get("/api/v1/services")

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()] == ["chatbot"]


def test_protected_usage_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/usage").status_code == 401
    assert client.get("/api/v1/history/conversations").status_code == 401
    assert client.get("/api/v1/services").status_code == 401
