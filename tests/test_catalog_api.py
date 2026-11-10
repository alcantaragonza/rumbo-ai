from sqlalchemy.orm import Session

from app.models import Activity, Destination

DESTINATION_PAYLOAD = {
    "name": "Antigua Guatemala",
    "description": "Ciudad colonial con iglesias y cafés.",
    "region": "Sacatepéquez",
    "country": "Guatemala",
    "latitude": 14.5586,
    "longitude": -90.7295,
    "interests": ["cultura", "gastronomia"],
    "season": "todo el año",
}


def test_user_cannot_create_destination(as_user) -> None:
    response = as_user.post("/api/v1/destinations", json=DESTINATION_PAYLOAD)

    assert response.status_code == 403


def test_user_cannot_request_inactive_records(as_user) -> None:
    response = as_user.get("/api/v1/destinations", params={"include_inactive": "true"})

    assert response.status_code == 403


def test_admin_can_crud_destination(as_admin) -> None:
    created = as_admin.post("/api/v1/destinations", json=DESTINATION_PAYLOAD)
    assert created.status_code == 201
    destination = created.json()
    destination_id = destination["id"]
    assert destination["name"] == "Antigua Guatemala"
    assert destination["activities"] == []

    listing = as_admin.get("/api/v1/destinations")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [destination_id]

    updated = as_admin.patch(
        f"/api/v1/destinations/{destination_id}",
        json={"name": "Antigua Colonial", "interests": ["cultura"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Antigua Colonial"
    assert updated.json()["interests"] == ["cultura"]

    deleted = as_admin.delete(f"/api/v1/destinations/{destination_id}")
    assert deleted.status_code == 204

    assert as_admin.get("/api/v1/destinations").json() == []
    assert as_admin.get(f"/api/v1/destinations/{destination_id}").status_code == 404

    inactive = as_admin.get(
        f"/api/v1/destinations/{destination_id}",
        params={"include_inactive": True},
    )
    assert inactive.status_code == 200
    assert inactive.json()["is_active"] is False


def test_admin_can_crud_activity(as_admin, db_session: Session) -> None:
    destination = Destination(
        name="Lago de Atitlán",
        description="Lago volcánico.",
        region="Sololá",
        country="Guatemala",
        interests=["naturaleza"],
        season="noviembre a abril",
    )
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    payload = {
        "destination_id": destination.id,
        "name": "Kayak en el lago",
        "description": "Paseo en kayak por la bahía.",
        "category": "aventura",
        "estimated_cost": 20,
        "duration_minutes": 120,
    }

    created = as_admin.post("/api/v1/activities", json=payload)
    assert created.status_code == 201
    activity_id = created.json()["id"]

    listing = as_admin.get(
        "/api/v1/activities", params={"destination_id": destination.id}
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [activity_id]

    updated = as_admin.patch(
        f"/api/v1/activities/{activity_id}", json={"estimated_cost": 25}
    )
    assert updated.status_code == 200
    assert updated.json()["estimated_cost"] == 25

    deleted = as_admin.delete(f"/api/v1/activities/{activity_id}")
    assert deleted.status_code == 204
    assert as_admin.get("/api/v1/activities").json() == []


def test_activities_of_inactive_destination_are_hidden(
    as_admin, db_session: Session
) -> None:
    destination = Destination(
        name="Destino oculto",
        description="Destino inactivo.",
        region="Petén",
        country="Guatemala",
        interests=["cultura"],
        season="todo el año",
        is_active=False,
    )
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    activity = Activity(
        destination_id=destination.id,
        name="Museo oculto",
        description="No debe listarse.",
        category="cultura",
        estimated_cost=5,
        is_active=True,
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)

    listing = as_admin.get(
        "/api/v1/activities", params={"destination_id": destination.id}
    )
    assert listing.status_code == 200
    assert listing.json() == []
    assert as_admin.get(f"/api/v1/activities/{activity.id}").status_code == 404
