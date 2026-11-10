import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.ai.llm import LLMClient
from app.ai.tools import (
    ToolStep,
    estimate_cost,
    estimate_distance,
    get_destination,
    get_weather,
    search_catalog,
)
from app.models import Activity, AiService, Destination, User
from app.services.usage import (
    estimate_tokens,
    get_user_tokens_used,
    run_ai_call,
)

MAX_STEPS = 6
ACTIVITIES_PER_DAY = 2


@dataclass(slots=True)
class AgentRequest:
    destination_id: int | None = None
    destination_query: str | None = None
    days: int = 2
    interests: list[str] = field(default_factory=list)
    budget: float | None = None
    travelers: int = 1
    origin_latitude: float | None = None
    origin_longitude: float | None = None
    change: str | None = None
    new_budget: float | None = None


@dataclass(slots=True)
class AgentResult:
    service_slug: str
    summary: str
    destination: dict[str, Any] | None
    days: int
    itinerary: list[dict[str, Any]]
    weather: dict[str, Any]
    distance_km: float | None
    estimated_cost: float
    currency: str
    budget: float | None
    within_budget: bool | None
    steps: list[dict[str, str]]
    sources: list[dict[str, Any]]
    warnings: list[str]
    missing_info: list[str]
    replaced: list[dict[str, Any]]
    tokens_total: int
    tokens_remaining: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_slug": self.service_slug,
            "summary": self.summary,
            "destination": self.destination,
            "days": self.days,
            "itinerary": self.itinerary,
            "weather": self.weather,
            "distance_km": self.distance_km,
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "budget": self.budget,
            "within_budget": self.within_budget,
            "steps": self.steps,
            "sources": self.sources,
            "warnings": self.warnings,
            "missing_info": self.missing_info,
            "replaced": self.replaced,
            "tokens_total": self.tokens_total,
            "tokens_remaining": self.tokens_remaining,
        }


def _add_step(
    steps: list[ToolStep], tool: str, status: str, detail: str
) -> None:
    if len(steps) >= MAX_STEPS:
        return
    steps.append(ToolStep(tool=tool, status=status, detail=detail))


def _resolve_destination(
    session: Session,
    request: AgentRequest,
    steps: list[ToolStep],
    warnings: list[str],
) -> Destination | None:
    if request.destination_id is not None:
        destination = get_destination(session, request.destination_id)
        _add_step(
            steps,
            "get_destination",
            "ok" if destination else "not_found",
            f"destino {request.destination_id}",
        )
        if destination is None:
            warnings.append("El destino solicitado no existe o está inactivo.")
        return destination

    if not request.destination_query and not request.interests:
        return None

    candidates = search_catalog(
        session,
        interests=None if request.destination_query else (request.interests or None),
        query=request.destination_query,
        limit=5,
    )
    _add_step(
        steps,
        "search_catalog",
        "ok" if candidates else "empty",
        f"{len(candidates)} candidatos",
    )
    if not candidates:
        warnings.append("No se encontraron destinos con esas preferencias.")
        return None
    return candidates[0]


def _select_activities(
    destination: Destination,
    *,
    interests: list[str],
    days: int,
    mode: str | None = None,
) -> list[Activity]:
    active = [activity for activity in destination.activities if activity.is_active]
    limit = days * ACTIVITIES_PER_DAY

    if mode == "budget":
        return sorted(active, key=lambda activity: float(activity.estimated_cost))[:limit]

    def score(activity: Activity) -> int:
        text = f"{activity.category} {activity.name} {activity.description}".lower()
        value = sum(1 for interest in interests if interest.lower() in text)
        if mode == "rain" and activity.category in {"cultura", "gastronomia"}:
            value += 2
        return value

    return sorted(active, key=score, reverse=True)[:limit]


def _activity_payload(activity: Activity) -> dict[str, Any]:
    return {
        "id": activity.id,
        "name": activity.name,
        "description": activity.description,
        "category": activity.category,
        "estimated_cost": float(activity.estimated_cost),
        "currency": activity.currency,
        "duration_minutes": activity.duration_minutes,
    }


def _build_itinerary(
    activities: list[Activity], days: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    itinerary: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for index, activity in enumerate(activities):
        day_number = index // ACTIVITIES_PER_DAY + 1
        if day_number > days:
            break
        while len(itinerary) < day_number:
            itinerary.append({"day": len(itinerary) + 1, "activities": []})
        payload = _activity_payload(activity)
        itinerary[day_number - 1]["activities"].append(payload)
        sources.append(
            {
                "type": "activity",
                "id": activity.id,
                "name": activity.name,
                "destination_id": activity.destination_id,
            }
        )
    return itinerary, sources


def _destination_payload(destination: Destination) -> dict[str, Any]:
    return {
        "id": destination.id,
        "name": destination.name,
        "description": destination.description,
        "region": destination.region,
        "country": destination.country,
        "latitude": destination.latitude,
        "longitude": destination.longitude,
    }


def _summarize(
    session: Session,
    *,
    user: User,
    service: AiService,
    llm: LLMClient,
    plan: dict[str, Any],
) -> tuple[str, int, int]:
    prompt = [
        {
            "role": "system",
            "content": (
                "Resume en 2 o 3 frases el itinerario y los cambios indicados. "
                "Menciona el clima solo si está verificado y sé claro con las "
                "advertencias."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(plan, ensure_ascii=False, default=str),
        },
    ]
    estimated = estimate_tokens(str(plan)) + 200
    record, result = run_ai_call(
        session,
        user=user,
        service=service,
        estimated_tokens=estimated,
        call=lambda: llm.complete(prompt, model=service.model, max_tokens=300),
    )
    used = get_user_tokens_used(session, user.id)
    return (
        result.content,
        record.tokens_in + record.tokens_out,
        max(user.token_limit - used, 0),
    )


def _missing_result(
    *,
    service: AiService,
    request: AgentRequest,
    steps: list[ToolStep],
    warnings: list[str],
    missing_info: list[str],
    session: Session,
    user: User,
) -> AgentResult:
    used = get_user_tokens_used(session, user.id)
    if "destination" in missing_info:
        summary = "Necesito que indiques un destino o algunas preferencias para preparar el plan."
    else:
        summary = "El destino no tiene actividades activas suficientes para el plan solicitado."
    return AgentResult(
        service_slug=service.slug,
        summary=summary,
        destination=None,
        days=request.days,
        itinerary=[],
        weather={"available": False, "reason": "not_consulted"},
        distance_km=None,
        estimated_cost=0.0,
        currency="USD",
        budget=request.budget,
        within_budget=None,
        steps=[step.to_dict() for step in steps],
        sources=[],
        warnings=warnings,
        missing_info=missing_info,
        replaced=[],
        tokens_total=0,
        tokens_remaining=max(user.token_limit - used, 0),
    )


def run_itinerary(
    session: Session,
    *,
    user: User,
    service: AiService,
    llm: LLMClient,
    request: AgentRequest,
    weather_fetcher: Callable[[float, float, int], dict[str, Any]] | None = None,
) -> AgentResult:
    steps: list[ToolStep] = []
    warnings: list[str] = []
    missing_info: list[str] = []

    destination = _resolve_destination(session, request, steps, warnings)
    if destination is None:
        return _missing_result(
            service=service,
            request=request,
            steps=steps,
            warnings=warnings,
            missing_info=["destination"],
            session=session,
            user=user,
        )

    activities = _select_activities(
        destination, interests=request.interests, days=request.days
    )
    _add_step(
        steps,
        "select_activities",
        "ok" if activities else "empty",
        f"{len(activities)} actividades",
    )
    if not activities:
        missing_info.append("activities")

    itinerary, sources = _build_itinerary(activities, request.days)
    sources.insert(0, {"type": "destination", "id": destination.id, "name": destination.name})

    weather: dict[str, Any]
    if destination.latitude is None or destination.longitude is None:
        weather = {"available": False, "reason": "no_coordinates"}
        warnings.append("El destino no tiene coordenadas; no se pudo consultar el clima.")
        _add_step(steps, "get_weather", "skipped", "sin coordenadas")
    else:
        weather = get_weather(
            session,
            destination.latitude,
            destination.longitude,
            days=request.days,
            fetcher=weather_fetcher,
        )
        _add_step(
            steps,
            "get_weather",
            "ok" if weather.get("available") else "degraded",
            "con caché" if weather.get("cached") else "consultado",
        )
        if not weather.get("available"):
            warnings.append(
                "No se pudo verificar el clima; el itinerario no lo usa como dato confirmado."
            )

    distance_km: float | None = None
    if (
        request.origin_latitude is not None
        and request.origin_longitude is not None
        and destination.latitude is not None
        and destination.longitude is not None
    ):
        distance_km = estimate_distance(
            request.origin_latitude,
            request.origin_longitude,
            destination.latitude,
            destination.longitude,
        )
        _add_step(steps, "estimate_distance", "ok", f"{distance_km} km")
    else:
        _add_step(steps, "estimate_distance", "skipped", "sin origen")

    total_cost = estimate_cost(
        [float(activity.estimated_cost) for activity in activities],
        travelers=request.travelers,
    )
    _add_step(steps, "estimate_cost", "ok", f"USD {total_cost}")

    within_budget: bool | None = None
    if request.budget is not None:
        within_budget = total_cost <= request.budget
        if not within_budget:
            warnings.append(
                f"El costo estimado (USD {total_cost}) supera el presupuesto "
                f"(USD {request.budget})."
            )

    plan = {
        "destination": _destination_payload(destination),
        "days": request.days,
        "itinerary": itinerary,
        "weather": weather,
        "distance_km": distance_km,
        "estimated_cost": total_cost,
        "currency": "USD",
        "warnings": warnings,
        "missing_info": missing_info,
    }

    if missing_info:
        return AgentResult(
            service_slug=service.slug,
            summary="Necesito más información para completar el itinerario.",
            destination=_destination_payload(destination),
            days=request.days,
            itinerary=itinerary,
            weather=weather,
            distance_km=distance_km,
            estimated_cost=total_cost,
            currency="USD",
            budget=request.budget,
            within_budget=within_budget,
            steps=[step.to_dict() for step in steps],
            sources=sources,
            warnings=warnings,
            missing_info=missing_info,
            replaced=[],
            tokens_total=0,
            tokens_remaining=max(
                user.token_limit - get_user_tokens_used(session, user.id), 0
            ),
        )

    summary, tokens_total, remaining = _summarize(
        session, user=user, service=service, llm=llm, plan=plan
    )
    return AgentResult(
        service_slug=service.slug,
        summary=summary,
        destination=_destination_payload(destination),
        days=request.days,
        itinerary=itinerary,
        weather=weather,
        distance_km=distance_km,
        estimated_cost=total_cost,
        currency="USD",
        budget=request.budget,
        within_budget=within_budget,
        steps=[step.to_dict() for step in steps],
        sources=sources,
        warnings=warnings,
        missing_info=[],
        replaced=[],
        tokens_total=tokens_total,
        tokens_remaining=remaining,
    )


def run_adjustment(
    session: Session,
    *,
    user: User,
    service: AiService,
    llm: LLMClient,
    request: AgentRequest,
    weather_fetcher: Callable[[float, float, int], dict[str, Any]] | None = None,
) -> AgentResult:
    steps: list[ToolStep] = []
    warnings: list[str] = []

    destination = _resolve_destination(session, request, steps, warnings)
    if destination is None:
        return _missing_result(
            service=service,
            request=request,
            steps=steps,
            warnings=warnings,
            missing_info=["destination"],
            session=session,
            user=user,
        )

    base_activities = _select_activities(
        destination, interests=request.interests, days=request.days
    )
    mode = "rain" if request.change == "rain" else "budget"
    adjusted = _select_activities(
        destination, interests=request.interests, days=request.days, mode=mode
    )
    if not adjusted:
        return _missing_result(
            service=service,
            request=request,
            steps=steps,
            warnings=warnings,
            missing_info=["activities"],
            session=session,
            user=user,
        )

    replaced: list[dict[str, Any]] = []
    base_ids = {activity.id for activity in base_activities}
    adjusted_ids = {activity.id for activity in adjusted}
    for activity in base_activities:
        if activity.id not in adjusted_ids:
            replacement = next(
                (item for item in adjusted if item.id not in base_ids), None
            )
            replaced.append(
                {
                    "removed": activity.name,
                    "added": replacement.name if replacement else None,
                    "reason": "clima" if mode == "rain" else "presupuesto",
                }
            )
    new_budget = request.new_budget if request.new_budget is not None else request.budget
    if mode == "budget" and new_budget is not None:
        kept: list[Activity] = []
        running = 0.0
        for activity in adjusted:
            cost = float(activity.estimated_cost) * max(request.travelers, 1)
            if running + cost <= new_budget:
                kept.append(activity)
                running += cost
        dropped = [activity for activity in adjusted if activity not in kept]
        for activity in dropped:
            replaced.append(
                {"removed": activity.name, "added": None, "reason": "presupuesto"}
            )
        if dropped:
            warnings.append(
                "Algunas actividades se quitaron para respetar el nuevo presupuesto."
            )
        adjusted = kept

    _add_step(steps, "adjust_activities", "ok", f"{len(replaced)} reemplazos")
    itinerary, sources = _build_itinerary(adjusted, request.days)
    sources.insert(0, {"type": "destination", "id": destination.id, "name": destination.name})

    weather: dict[str, Any]
    if destination.latitude is None or destination.longitude is None:
        weather = {"available": False, "reason": "no_coordinates"}
    else:
        weather = get_weather(
            session,
            destination.latitude,
            destination.longitude,
            days=request.days,
            fetcher=weather_fetcher,
        )
        _add_step(
            steps,
            "get_weather",
            "ok" if weather.get("available") else "degraded",
            "con caché" if weather.get("cached") else "consultado",
        )

    total_cost = estimate_cost(
        [float(activity.estimated_cost) for activity in adjusted],
        travelers=request.travelers,
    )
    _add_step(steps, "estimate_cost", "ok", f"USD {total_cost}")

    within_budget: bool | None = None
    if new_budget is not None:
        within_budget = total_cost <= new_budget
        if not within_budget:
            warnings.append(
                f"No fue posible ajustar todo el plan a USD {new_budget}; "
                f"el costo estimado es USD {total_cost}."
            )

    plan = {
        "destination": _destination_payload(destination),
        "days": request.days,
        "itinerary": itinerary,
        "weather": weather,
        "estimated_cost": total_cost,
        "currency": "USD",
        "budget": new_budget,
        "replaced": replaced,
        "warnings": warnings,
    }
    summary, tokens_total, remaining = _summarize(
        session, user=user, service=service, llm=llm, plan=plan
    )
    return AgentResult(
        service_slug=service.slug,
        summary=summary,
        destination=_destination_payload(destination),
        days=request.days,
        itinerary=itinerary,
        weather=weather,
        distance_km=None,
        estimated_cost=total_cost,
        currency="USD",
        budget=new_budget,
        within_budget=within_budget,
        steps=[step.to_dict() for step in steps],
        sources=sources,
        warnings=warnings,
        missing_info=[],
        replaced=replaced,
        tokens_total=tokens_total,
        tokens_remaining=remaining,
    )
