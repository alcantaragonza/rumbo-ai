from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User

USER_PAYLOAD = {
    "email": "nuevo@rumbo.ai",
    "password": "Password123!",
    "full_name": "Usuario Nuevo",
    "role": "user",
    "token_limit": 5000,
}


def test_admin_can_crud_users(as_admin) -> None:
    created = as_admin.post("/api/v1/users", json=USER_PAYLOAD)
    assert created.status_code == 201
    user = created.json()
    user_id = user["id"]
    assert user["email"] == "nuevo@rumbo.ai"
    assert user["token_limit"] == 5000

    listing = as_admin.get("/api/v1/users")
    assert listing.status_code == 200
    assert user_id in [item["id"] for item in listing.json()]

    updated = as_admin.patch(
        f"/api/v1/users/{user_id}",
        json={"full_name": "Usuario Actualizado", "token_limit": 9000},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Usuario Actualizado"
    assert updated.json()["token_limit"] == 9000

    deactivated = as_admin.delete(f"/api/v1/users/{user_id}")
    assert deactivated.status_code == 204
    assert as_admin.get(f"/api/v1/users/{user_id}").json()["is_active"] is False


def test_duplicate_email_is_rejected(as_admin) -> None:
    assert as_admin.post("/api/v1/users", json=USER_PAYLOAD).status_code == 201

    duplicate = as_admin.post(
        "/api/v1/users",
        json={**USER_PAYLOAD, "email": "NUEVO@RUMBO.AI"},
    )

    assert duplicate.status_code == 409


def test_regular_user_cannot_manage_users(as_user) -> None:
    assert as_user.get("/api/v1/users").status_code == 403
    assert as_user.post("/api/v1/users", json=USER_PAYLOAD).status_code == 403


def test_admin_cannot_deactivate_self(as_admin, admin_user: User) -> None:
    response = as_admin.delete(f"/api/v1/users/{admin_user.id}")

    assert response.status_code == 400


def test_deactivated_user_cannot_login(
    as_admin, client: TestClient, db_session: Session
) -> None:
    created = as_admin.post("/api/v1/users", json=USER_PAYLOAD)
    user_id = created.json()["id"]
    assert as_admin.delete(f"/api/v1/users/{user_id}").status_code == 204

    response = client.post(
        "/api/v1/auth/login",
        json={"email": USER_PAYLOAD["email"], "password": USER_PAYLOAD["password"]},
    )

    assert response.status_code == 401
