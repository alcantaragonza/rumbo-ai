from sqlalchemy.orm import Session

from app.ai.embeddings import HashEmbeddingClient
from app.ai.retrieval import retrieve
from app.models import Activity, Destination

embedder = HashEmbeddingClient()


def make_destination(
    session: Session,
    *,
    name: str,
    description: str,
    region: str = "Sacatepéquez",
    interests: list[str] | None = None,
    is_active: bool = True,
) -> Destination:
    interests = interests or []
    text = " ".join(
        [name, description, region, "Guatemala", " ".join(interests), "todo el año"]
    )
    destination = Destination(
        name=name,
        description=description,
        region=region,
        country="Guatemala",
        interests=interests,
        season="todo el año",
        is_active=is_active,
        embedding=embedder.embed([text])[0],
    )
    session.add(destination)
    session.commit()
    session.refresh(destination)
    return destination


def make_activity(
    session: Session,
    destination: Destination,
    *,
    name: str,
    description: str,
    category: str,
    is_active: bool = True,
) -> Activity:
    text = " ".join([name, description, category, destination.name])
    activity = Activity(
        destination_id=destination.id,
        name=name,
        description=description,
        category=category,
        estimated_cost=10,
        is_active=is_active,
        embedding=embedder.embed([text])[0],
    )
    session.add(activity)
    session.commit()
    session.refresh(activity)
    return activity


def test_retrieves_destination(db_session: Session) -> None:
    destination = make_destination(
        db_session,
        name="Antigua Guatemala",
        description="Ciudad colonial con iglesias y cafés.",
        interests=["cultura", "historia"],
    )

    items = retrieve(db_session, "Antigua Guatemala cultura")

    assert any(
        item.kind == "destination" and item.id == destination.id for item in items
    )


def test_retrieves_activity_with_destination(db_session: Session) -> None:
    destination = make_destination(
        db_session,
        name="Lago de Atitlán",
        description="Lago volcánico.",
        region="Sololá",
        interests=["naturaleza"],
    )
    activity = make_activity(
        db_session,
        destination,
        name="Kayak en el lago",
        description="Paseo en kayak por la bahía.",
        category="aventura",
    )

    items = retrieve(db_session, "kayak")

    match = next(item for item in items if item.kind == "activity")
    assert match.id == activity.id
    assert match.destination_name == "Lago de Atitlán"


def test_inactive_records_are_excluded(db_session: Session) -> None:
    inactive_destination = make_destination(
        db_session,
        name="Antigua Oculta",
        description="No debe aparecer.",
        is_active=False,
    )
    active_destination = make_destination(
        db_session,
        name="Antigua Visible",
        description="Sí debe aparecer.",
    )
    make_activity(
        db_session,
        active_destination,
        name="Kayak oculto",
        description="Actividad inactiva.",
        category="aventura",
        is_active=False,
    )

    items = retrieve(db_session, "Antigua")
    ids = {item.id for item in items if item.kind == "destination"}

    assert inactive_destination.id not in ids
    assert active_destination.id in ids
    assert all(item.name != "Kayak oculto" for item in items)


def test_no_match_returns_empty(db_session: Session) -> None:
    make_destination(
        db_session,
        name="Lago de Atitlán",
        description="Lago volcánico.",
    )
    make_destination(
        db_session,
        name="Cerro de la Cruz",
        description="Mirador con vista.",
    )

    assert retrieve(db_session, "playa de Marte") == []


def test_falls_back_to_fts_when_embeddings_fail(db_session: Session) -> None:
    destination = make_destination(
        db_session,
        name="Antigua Guatemala",
        description="Ciudad colonial con iglesias.",
    )

    class FailingEmbedder:
        dimension = 384

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("sin embeddings")

    items = retrieve(db_session, "Antigua", embedder=FailingEmbedder())

    assert any(
        item.kind == "destination" and item.id == destination.id for item in items
    )
    assert all("vector" not in item.sources for item in items)
