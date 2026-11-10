"""Carga datos de demostración de forma idempotente."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import HashEmbeddingClient
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Activity, AiService, Destination, User

USERS: list[dict[str, str]] = [
    {
        "email": "admin@rumbo.ai",
        "password": "Admin123!",
        "full_name": "Administrador Rumbo AI",
        "role": "admin",
    },
    {
        "email": "user@rumbo.ai",
        "password": "User123!",
        "full_name": "Usuario Demo",
        "role": "user",
    },
]

DESTINATIONS: list[dict[str, Any]] = [
    {
        "name": "Antigua Guatemala",
        "description": (
            "Ciudad colonial con calles empedradas, iglesias históricas, cafés y "
            "mercados de artesanía."
        ),
        "region": "Sacatepéquez",
        "country": "Guatemala",
        "latitude": 14.5586,
        "longitude": -90.7295,
        "interests": ["cultura", "historia", "gastronomia"],
        "season": "todo el año",
        "activities": [
            {
                "name": "Caminata por el centro histórico",
                "description": "Recorrido guiado por el parque central y sus iglesias.",
                "category": "cultura",
                "estimated_cost": Decimal("15.00"),
                "duration_minutes": 120,
            },
            {
                "name": "Tour de cafés y gastronomía",
                "description": "Degustación de café de altura y platos típicos.",
                "category": "gastronomia",
                "estimated_cost": Decimal("35.00"),
                "duration_minutes": 180,
            },
            {
                "name": "Ascenso al Cerro de la Cruz",
                "description": "Caminata corta con vista panorámica de la ciudad.",
                "category": "naturaleza",
                "estimated_cost": Decimal("10.00"),
                "duration_minutes": 90,
            },
        ],
    },
    {
        "name": "Lago de Atitlán",
        "description": (
            "Lago volcánico rodeado de pueblos mayas, ideal para kayak, caminatas "
            "y fotografía."
        ),
        "region": "Sololá",
        "country": "Guatemala",
        "latitude": 14.6907,
        "longitude": -91.2025,
        "interests": ["naturaleza", "aventura", "fotografia"],
        "season": "noviembre a abril",
        "activities": [
            {
                "name": "Kayak en el lago",
                "description": "Paseo en kayak por la bahía con equipo incluido.",
                "category": "aventura",
                "estimated_cost": Decimal("20.00"),
                "duration_minutes": 120,
            },
            {
                "name": "Visita a Santiago Atitlán",
                "description": "Recorrido por el pueblo, su iglesia y mercado local.",
                "category": "cultura",
                "estimated_cost": Decimal("25.00"),
                "duration_minutes": 240,
            },
            {
                "name": "Mirador del Volcán San Pedro",
                "description": "Caminata al mirador con vistas al lago y los volcanes.",
                "category": "naturaleza",
                "estimated_cost": Decimal("30.00"),
                "duration_minutes": 180,
            },
        ],
    },
]


SERVICES: list[dict[str, Any]] = [
    {
        "slug": "chatbot",
        "name": "Chatbot de viajes",
        "kind": "chatbot",
        "model": "openai/gpt-oss-20b",
        "system_prompt": (
            "Eres un asistente turístico. Responde solo con información del "
            "catálogo recuperado y cita las fuentes."
        ),
    },
    {
        "slug": "itinerary-planner",
        "name": "Planificador de itinerarios",
        "kind": "agent",
        "model": "openai/gpt-oss-20b",
        "system_prompt": (
            "Construye itinerarios combinando el catálogo con clima y distancias. "
            "Explica los pasos y las fuentes."
        ),
    },
    {
        "slug": "trip-adjuster",
        "name": "Ajuste de viaje",
        "kind": "agent",
        "model": "openai/gpt-oss-20b",
        "system_prompt": (
            "Ajusta un itinerario ante cambios de clima o presupuesto, indicando "
            "qué actividades reemplazaste."
        ),
    },
]


def embed_catalog(session: Session) -> int:
    """Calcula embeddings faltantes del catálogo."""
    session.flush()
    embedder = HashEmbeddingClient()
    updated = 0

    for destination in session.scalars(select(Destination)).all():
        if destination.embedding is None:
            text = " ".join(
                [
                    destination.name,
                    destination.description,
                    destination.region,
                    destination.country,
                    " ".join(destination.interests),
                    destination.season or "",
                ]
            )
            destination.embedding = embedder.embed([text])[0]
            updated += 1

    for activity in session.scalars(select(Activity)).all():
        if activity.embedding is None:
            destination = activity.destination
            text = " ".join(
                [
                    activity.name,
                    activity.description,
                    activity.category,
                    destination.name if destination is not None else "",
                ]
            )
            activity.embedding = embedder.embed([text])[0]
            updated += 1

    session.flush()
    return updated


def seed(session: Session) -> dict[str, int]:
    """Crea usuarios, destinos, actividades y servicios que aún no existan."""
    created = {"users": 0, "destinations": 0, "activities": 0, "services": 0}

    for user_data in USERS:
        existing_user = session.scalar(
            select(User).where(User.email == user_data["email"])
        )
        if existing_user is None:
            session.add(
                User(
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                )
            )
            created["users"] += 1

    for destination_data in DESTINATIONS:
        destination = session.scalar(
            select(Destination).where(Destination.name == destination_data["name"])
        )
        if destination is None:
            destination = Destination(
                name=destination_data["name"],
                description=destination_data["description"],
                region=destination_data["region"],
                country=destination_data["country"],
                latitude=destination_data["latitude"],
                longitude=destination_data["longitude"],
                interests=destination_data["interests"],
                season=destination_data["season"],
            )
            session.add(destination)
            session.flush()
            created["destinations"] += 1

        for activity_data in destination_data["activities"]:
            activity = session.scalar(
                select(Activity).where(
                    Activity.destination_id == destination.id,
                    Activity.name == activity_data["name"],
                )
            )
            if activity is None:
                session.add(
                    Activity(
                        destination_id=destination.id,
                        currency="USD",
                        **activity_data,
                    )
                )
                created["activities"] += 1

    for service_data in SERVICES:
        existing_service = session.scalar(
            select(AiService).where(AiService.slug == service_data["slug"])
        )
        if existing_service is None:
            session.add(AiService(**service_data))
            created["services"] += 1

    embedded = embed_catalog(session)
    session.commit()
    created["embeddings"] = embedded
    return created


def main() -> None:
    with SessionLocal() as session:
        created = seed(session)
    print(
        "Seed completado: "
        f"{created['users']} usuarios, "
        f"{created['destinations']} destinos, "
        f"{created['activities']} actividades, "
        f"{created['services']} servicios y "
        f"{created['embeddings']} embeddings nuevos."
    )


if __name__ == "__main__":
    main()
