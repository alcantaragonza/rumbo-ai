from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import AiService, User
from app.services.usage import record_ai_request


def make_user(session: Session, email: str) -> User:
    user = User(
        email=email,
        password_hash="not-used",
        full_name=email,
        role="user",
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


def add_request(
    session: Session,
    *,
    user: User,
    service: AiService,
    created_at: datetime,
    tokens_in: int = 0,
    tokens_out: int = 0,
    status: str = "ok",
) -> None:
    record = record_ai_request(
        session,
        user_id=user.id,
        service_id=service.id,
        status=status,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    record.created_at = created_at
    session.commit()


def seed_requests(session: Session, primary: User) -> dict[str, object]:
    chatbot = make_service(session, "chatbot", "Chatbot")
    planner = make_service(session, "itinerary-planner", "Planificador")
    admin = primary
    other = make_user(session, "report-other@rumbo.ai")

    add_request(
        session,
        user=admin,
        service=chatbot,
        created_at=datetime(2026, 11, 9, 23, 30, tzinfo=UTC),
        tokens_in=10,
        tokens_out=5,
    )
    add_request(
        session,
        user=admin,
        service=chatbot,
        created_at=datetime(2026, 11, 10, 1, 0, tzinfo=UTC),
        tokens_in=20,
        tokens_out=10,
    )
    add_request(
        session,
        user=other,
        service=planner,
        created_at=datetime(2026, 11, 10, 12, 0, tzinfo=UTC),
        tokens_in=30,
        tokens_out=15,
    )
    add_request(
        session,
        user=admin,
        service=planner,
        created_at=datetime(2026, 11, 10, 13, 0, tzinfo=UTC),
        status="blocked",
    )
    return {"chatbot": chatbot, "planner": planner, "admin": admin, "other": other}


def test_admin_report_groups_by_day_service_and_user(
    as_admin, db_session: Session, admin_user: User
) -> None:
    data = seed_requests(db_session, admin_user)

    response = as_admin.get("/api/v1/reports/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "UTC"
    assert body["currency"] == "USD"
    assert len(body["rows"]) == 4
    assert body["totals"] == {
        "requests": 4,
        "blocked": 1,
        "tokens_in": 60,
        "tokens_out": 30,
        "tokens_total": 90,
    }
    dates = [(row["date"], row["service_slug"]) for row in body["rows"]]
    assert ("2026-11-09", "chatbot") in dates
    assert ("2026-11-10", "itinerary-planner") in dates

    filtered = as_admin.get(
        "/api/v1/reports/usage", params={"service_id": data["chatbot"].id}
    )
    assert filtered.status_code == 200
    assert filtered.json()["totals"]["requests"] == 2
    assert filtered.json()["totals"]["tokens_total"] == 45

    by_user = as_admin.get(
        "/api/v1/reports/usage", params={"user_id": data["other"].id}
    )
    assert by_user.status_code == 200
    assert len(by_user.json()["rows"]) == 1
    assert by_user.json()["totals"]["tokens_total"] == 45

    by_date = as_admin.get(
        "/api/v1/reports/usage",
        params={"date_from": "2026-11-10T00:00:00Z"},
    )
    assert by_date.status_code == 200
    assert len(by_date.json()["rows"]) == 3


def test_user_report_is_scoped(
    as_user, db_session: Session, regular_user: User
) -> None:
    data = seed_requests(db_session, regular_user)

    response = as_user.get("/api/v1/reports/usage")

    assert response.status_code == 200
    body = response.json()
    assert {row["user_email"] for row in body["rows"]} == {regular_user.email}

    forbidden = as_user.get(
        "/api/v1/reports/usage", params={"user_id": data["other"].id}
    )
    assert forbidden.status_code == 403


def test_report_totals_match_usage_summary(
    as_admin, db_session: Session, admin_user: User
) -> None:
    data = seed_requests(db_session, admin_user)
    service_id = data["chatbot"].id

    report = as_admin.get(
        "/api/v1/reports/usage", params={"service_id": service_id}
    )
    usage = as_admin.get("/api/v1/usage", params={"service_id": service_id})

    assert report.status_code == 200
    assert usage.status_code == 200
    assert report.json()["totals"]["requests"] == usage.json()["requests"]
    assert report.json()["totals"]["tokens_total"] == usage.json()["tokens_total"]


def test_report_requires_authentication(client) -> None:
    assert client.get("/api/v1/reports/usage").status_code == 401
