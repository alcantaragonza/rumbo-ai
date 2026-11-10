from typing import Any

from pydantic import BaseModel, Field


class AgentRequestBase(BaseModel):
    destination_id: int | None = None
    destination_query: str | None = Field(default=None, max_length=200)
    days: int = Field(default=2, ge=1, le=7)
    interests: list[str] = Field(default_factory=list)
    budget: float | None = Field(default=None, ge=0)
    travelers: int = Field(default=1, ge=1, le=20)
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)


class ItineraryRequest(AgentRequestBase):
    pass


class AdjustRequest(AgentRequestBase):
    change: str = Field(default="rain", pattern="^(rain|budget)$")
    new_budget: float | None = Field(default=None, ge=0)


class AgentResponse(BaseModel):
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
