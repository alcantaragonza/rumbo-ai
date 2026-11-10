import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiRequest, AiService, User
from app.services.usage import (
    AiCallResult,
    QuotaExceeded,
    enforce_quota,
    estimate_tokens,
    get_user_tokens_used,
    record_ai_request,
    run_ai_call,
    usage_summary,
)


def make_user(session: Session, *, email: str, token_limit: int = 100) -> User:
    user = User(
        email=email,
        password_hash="not-used",
        full_name="Usuario de prueba",
        role="user",
        token_limit=token_limit,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_service(session: Session, *, slug: str = "chatbot") -> AiService:
    service = AiService(slug=slug, name=f"Servicio {slug}", kind="chatbot")
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def test_estimate_tokens() -> None:
    assert estimate_tokens("hola") == 1
    assert estimate_tokens("x" * 40) == 10


def test_blocked_request_is_recorded_and_call_is_not_executed(
    db_session: Session,
) -> None:
    user = make_user(db_session, email="quota@rumbo.ai", token_limit=50)
    service = make_service(db_session)
    record_ai_request(
        db_session,
        user_id=user.id,
        service_id=service.id,
        status="ok",
        tokens_in=30,
        tokens_out=10,
    )
    assert get_user_tokens_used(db_session, user.id) == 40

    called = {"value": False}

    def fake_call() -> AiCallResult:
        called["value"] = True
        return AiCallResult(tokens_in=1, tokens_out=1)

    with pytest.raises(QuotaExceeded) as exc_info:
        run_ai_call(
            db_session,
            user=user,
            service=service,
            estimated_tokens=20,
            call=fake_call,
        )

    assert exc_info.value.status_code == 429
    assert called["value"] is False
    blocked = db_session.scalar(
        select(AiRequest).where(
            AiRequest.user_id == user.id, AiRequest.status == "blocked"
        )
    )
    assert blocked is not None
    assert blocked.error_code == "quota_exceeded"
    assert get_user_tokens_used(db_session, user.id) == 40


def test_successful_call_records_usage(db_session: Session) -> None:
    user = make_user(db_session, email="ok@rumbo.ai", token_limit=100)
    service = make_service(db_session)

    record, result = run_ai_call(
        db_session,
        user=user,
        service=service,
        estimated_tokens=5,
        call=lambda: AiCallResult(tokens_in=7, tokens_out=3),
    )

    assert result.tokens_total == 10
    assert record.status == "ok"
    assert record.tokens_in == 7
    assert record.tokens_out == 3
    assert get_user_tokens_used(db_session, user.id) == 10


def test_usage_summary_groups_by_service(db_session: Session) -> None:
    user = make_user(db_session, email="summary@rumbo.ai", token_limit=1000)
    chatbot = make_service(db_session, slug="chatbot")
    agents = make_service(db_session, slug="itinerary-planner")
    record_ai_request(
        db_session,
        user_id=user.id,
        service_id=chatbot.id,
        status="ok",
        tokens_in=10,
        tokens_out=5,
    )
    record_ai_request(
        db_session,
        user_id=user.id,
        service_id=agents.id,
        status="ok",
        tokens_in=20,
        tokens_out=10,
    )

    summary = usage_summary(db_session, user_id=user.id)

    assert summary.requests == 2
    assert summary.tokens_total == 45
    assert {item.service_slug for item in summary.by_service} == {
        "chatbot",
        "itinerary-planner",
    }


def test_quota_check_returns_429_and_blocked_record(as_user, db_session: Session) -> None:
    service = make_service(db_session, slug="chatbot")
    user = db_session.scalar(select(User).where(User.email == "user-test@rumbo.ai"))
    assert user is not None
    user.token_limit = 10
    db_session.commit()
    record_ai_request(
        db_session,
        user_id=user.id,
        service_id=service.id,
        status="ok",
        tokens_in=10,
    )

    response = as_user.post(
        "/api/v1/ai/quota-check",
        json={"service_id": service.id, "estimated_tokens": 5},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "quota_exceeded"


def test_admin_updates_limit_and_it_takes_effect(
    as_admin, regular_user: User, db_session: Session
) -> None:
    regular_user.token_limit = 10
    db_session.commit()
    service = make_service(db_session)
    record_ai_request(
        db_session,
        user_id=regular_user.id,
        service_id=service.id,
        status="ok",
        tokens_in=10,
    )

    with pytest.raises(QuotaExceeded):
        enforce_quota(
            db_session,
            regular_user,
            service_id=service.id,
            estimated_tokens=1,
        )

    response = as_admin.patch(
        f"/api/v1/users/{regular_user.id}", json={"token_limit": 1000}
    )
    assert response.status_code == 200
    db_session.refresh(regular_user)

    enforce_quota(
        db_session,
        regular_user,
        service_id=service.id,
        estimated_tokens=1,
    )
