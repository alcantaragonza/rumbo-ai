import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Activity, Destination
from app.services.cache import get_cache, set_cache
from app.services.catalog import get_destination as get_destination_service
from app.services.catalog import search_destinations

WEATHER_CACHE_TTL_SECONDS = 1800


@dataclass(slots=True)
class ToolStep:
    tool: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"tool": self.tool, "status": self.status, "detail": self.detail}


def estimate_distance(
    latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float
) -> float:
    """Distancia Haversine en kilómetros."""
    radius_km = 6371.0
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return round(2 * radius_km * math.asin(math.sqrt(haversine)), 2)


def estimate_cost(costs: list[float], travelers: int = 1) -> float:
    return round(sum(costs) * max(travelers, 1), 2)


def search_catalog(
    session: Session,
    *,
    interests: list[str] | None = None,
    location: str | None = None,
    max_cost: float | None = None,
    season: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> list[Destination]:
    return search_destinations(
        session,
        interests=interests,
        location=location,
        max_cost=max_cost,
        season=season,
        q=query,
        limit=limit,
    )


def get_destination(session: Session, destination_id: int) -> Destination | None:
    return get_destination_service(session, destination_id)


def _fetch_open_meteo(
    latitude: float, longitude: float, days: int
) -> dict[str, Any]:
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,weathercode"
            ),
            "forecast_days": days,
            "timezone": "auto",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_weather(
    session: Session,
    latitude: float,
    longitude: float,
    *,
    days: int = 3,
    fetcher: Callable[[float, float, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Obtiene clima con caché; si la fuente falla, degrada sin inventar."""
    key = f"{latitude:.4f}:{longitude:.4f}:{days}"
    cached = get_cache(session, "open-meteo", key)
    if cached is not None:
        return {"available": True, "cached": True, **cached}

    fetch = fetcher or _fetch_open_meteo
    try:
        data = fetch(latitude, longitude, days)
    except Exception as exc:  # noqa: BLE001 - se reporta como dato no verificado
        return {"available": False, "cached": False, "error": str(exc)}

    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "days": days,
        "daily": data.get("daily", {}),
    }
    set_cache(
        session,
        "open-meteo",
        key,
        payload,
        ttl_seconds=WEATHER_CACHE_TTL_SECONDS,
    )
    return {"available": True, "cached": False, **payload}


def activity_cost(activity: Activity) -> float:
    return float(activity.estimated_cost)
