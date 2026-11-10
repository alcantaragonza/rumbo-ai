from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingClient, get_embedding_client
from app.models import Activity, Destination


@dataclass(slots=True)
class RetrievedItem:
    kind: str
    id: int
    name: str
    description: str
    destination_id: int | None
    destination_name: str | None
    score: float = 0.0
    sources: set[str] = field(default_factory=set)

    def to_source(self) -> dict[str, object]:
        return {
            "type": self.kind,
            "id": self.id,
            "name": self.name,
            "destination_id": self.destination_id,
            "destination_name": self.destination_name,
        }


def _destination_document():
    return func.concat_ws(
        " ",
        Destination.name,
        Destination.description,
        Destination.region,
        Destination.country,
        func.array_to_string(Destination.interests, " "),
        Destination.season,
    )


def _activity_document():
    return func.concat_ws(
        " ",
        Activity.name,
        Activity.description,
        Activity.category,
        Destination.name,
    )


def retrieve(
    session: Session,
    query: str,
    *,
    limit: int = 6,
    min_score: float = 0.01,
    embedder: EmbeddingClient | None = None,
) -> list[RetrievedItem]:
    """Combina búsqueda full-text y similitud vectorial sobre datos activos."""
    if not query.strip():
        return []

    embedder = embedder or get_embedding_client()
    items: dict[tuple[str, int], RetrievedItem] = {}

    def add(
        item: RetrievedItem,
        score: float,
        source: str,
    ) -> None:
        key = (item.kind, item.id)
        existing = items.get(key)
        if existing is None:
            existing = item
            items[key] = existing
        existing.score += float(score)
        existing.sources.add(source)

    tsquery = func.plainto_tsquery("spanish", query)

    destination_rank = func.ts_rank(
        func.to_tsvector("spanish", _destination_document()), tsquery
    )
    destination_stmt = (
        select(Destination, destination_rank.label("score"))
        .where(Destination.is_active.is_(True), destination_rank > 0)
        .order_by(destination_rank.desc())
        .limit(limit)
    )
    for destination, score in session.execute(destination_stmt).all():
        add(
            RetrievedItem(
                kind="destination",
                id=destination.id,
                name=destination.name,
                description=destination.description,
                destination_id=destination.id,
                destination_name=destination.name,
            ),
            score,
            "fts",
        )

    activity_rank = func.ts_rank(
        func.to_tsvector("spanish", _activity_document()), tsquery
    )
    activity_stmt = (
        select(Activity, Destination, activity_rank.label("score"))
        .join(Destination, Destination.id == Activity.destination_id)
        .where(
            Activity.is_active.is_(True),
            Destination.is_active.is_(True),
            activity_rank > 0,
        )
        .order_by(activity_rank.desc())
        .limit(limit)
    )
    for activity, destination, score in session.execute(activity_stmt).all():
        add(
            RetrievedItem(
                kind="activity",
                id=activity.id,
                name=activity.name,
                description=activity.description,
                destination_id=destination.id,
                destination_name=destination.name,
            ),
            score,
            "fts",
        )

    try:
        query_vector = embedder.embed([query])[0]
    except Exception:
        query_vector = None

    if query_vector is not None:
        destination_distance = Destination.embedding.cosine_distance(query_vector)
        destination_vector_stmt = (
            select(Destination, (1 - destination_distance).label("score"))
            .where(
                Destination.is_active.is_(True),
                Destination.embedding.is_not(None),
                (1 - destination_distance) >= min_score,
            )
            .order_by(destination_distance)
            .limit(limit)
        )
        for destination, score in session.execute(destination_vector_stmt).all():
            add(
                RetrievedItem(
                    kind="destination",
                    id=destination.id,
                    name=destination.name,
                    description=destination.description,
                    destination_id=destination.id,
                    destination_name=destination.name,
                ),
                score,
                "vector",
            )

        activity_distance = Activity.embedding.cosine_distance(query_vector)
        activity_vector_stmt = (
            select(Activity, Destination, (1 - activity_distance).label("score"))
            .join(Destination, Destination.id == Activity.destination_id)
            .where(
                Activity.is_active.is_(True),
                Destination.is_active.is_(True),
                Activity.embedding.is_not(None),
                (1 - activity_distance) >= min_score,
            )
            .order_by(activity_distance)
            .limit(limit)
        )
        for activity, destination, score in session.execute(
            activity_vector_stmt
        ).all():
            add(
                RetrievedItem(
                    kind="activity",
                    id=activity.id,
                    name=activity.name,
                    description=activity.description,
                    destination_id=destination.id,
                    destination_name=destination.name,
                ),
                score,
                "vector",
            )

    ranked = sorted(items.values(), key=lambda item: item.score, reverse=True)
    return [item for item in ranked if item.score >= min_score][:limit]


def format_context(items: list[RetrievedItem]) -> str:
    lines = []
    for index, item in enumerate(items, start=1):
        location = (
            f" en {item.destination_name}"
            if item.kind == "activity" and item.destination_name
            else ""
        )
        lines.append(
            f"[{index}] {item.kind}{location}: {item.name} — {item.description}"
        )
    return "\n".join(lines)
