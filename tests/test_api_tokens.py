from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User

DESTINATION_PAYLOAD = {
    "name": "Destino Token",
    "description": "Prueba de token de escritura.",
    "region": "Prueba",
    "country": "Guatemala",
    "interests": ["prueba"],
    "season": "todo el año",
}


def login_admin(client: TestClient, db_session: Session) -> User:
    user = db_session.scalar(
        select(User).where(User.email == "token-admin@rumbo.ai")
    )
    if user is None:
        user = User(
            email="token-admin@rumbo.ai",
            password_hash=hash_password("Secret123!"),
            full_name="Token Admin",
            role="admin",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Secret123!"},
    )
    assert response.status_code == 200
    return user


def test_creates_and_uses_read_token(client: TestClient, db_session: Session) -> None:
    login_admin(client, db_session)

    created = client.post(
        "/api/v1/auth/tokens",
        json={"name": "power-bi", "scope": "read"},
    )
    assert created.status_code == 201
    payload = created.json()
    token = payload["token"]
    assert token.startswith("rumbo_")
    assert payload["scope"] == "read"

    listing = client.get("/api/v1/auth/tokens")
    assert listing.status_code == 200
    assert listing.json()[0]["name"] == "power-bi"
    assert "token" not in listing.json()[0]

    client.cookies.clear()
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200

    write = client.post(
        "/api/v1/destinations",
        json=DESTINATION_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert write.status_code == 403

    client.cookies.clear()
    login_admin(client, db_session)
    revoked = client.delete(f"/api/v1/auth/tokens/{payload['id']}")
    assert revoked.status_code == 204

    client.cookies.clear()
    after_revoke = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert after_revoke.status_code == 401


def test_write_token_can_create_destination(
    client: TestClient, db_session: Session
) -> None:
    login_admin(client, db_session)
    created = client.post(
        "/api/v1/auth/tokens",
        json={"name": "postman", "scope": "write"},
    )
    token = created.json()["token"]

    client.cookies.clear()
    response = client.post(
        "/api/v1/destinations",
        json=DESTINATION_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


def test_missing_or_invalid_token_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer rumbo_invalido"},
        ).status_code
        == 401
    )
