from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.services.auth import SESSION_COOKIE


def create_user(db_session: Session, *, is_active: bool = True) -> User:
    user = User(
        email="login@rumbo.ai",
        password_hash=hash_password("Secret123!"),
        full_name="Login Test",
        role="admin",
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_and_me(client: TestClient, db_session: Session) -> None:
    create_user(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN@rumbo.ai", "password": "Secret123!"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert SESSION_COOKIE in client.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "login@rumbo.ai"


def test_login_with_invalid_password(client: TestClient, db_session: Session) -> None:
    create_user(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@rumbo.ai", "password": "incorrecta"},
    )

    assert response.status_code == 401


def test_inactive_user_cannot_login(client: TestClient, db_session: Session) -> None:
    create_user(db_session, is_active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@rumbo.ai", "password": "Secret123!"},
    )

    assert response.status_code == 401


def test_logout_revokes_session(client: TestClient, db_session: Session) -> None:
    create_user(db_session)
    client.post(
        "/api/v1/auth/login",
        json={"email": "login@rumbo.ai", "password": "Secret123!"},
    )

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
