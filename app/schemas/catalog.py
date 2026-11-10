from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActivityBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(min_length=2)
    category: str = Field(min_length=2, max_length=60)
    estimated_cost: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    duration_minutes: int = Field(default=60, gt=0)
    is_active: bool = True

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ActivityCreate(ActivityBase):
    destination_id: int


class ActivityUpdate(BaseModel):
    destination_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, min_length=2)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    estimated_cost: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    duration_minutes: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ActivityRead(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    destination_id: int
    created_at: datetime
    updated_at: datetime


class DestinationBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(min_length=2)
    region: str = Field(min_length=2, max_length=120)
    country: str = Field(min_length=2, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    interests: list[str] = Field(default_factory=list)
    season: str | None = Field(default=None, max_length=120)
    is_active: bool = True


class DestinationCreate(DestinationBase):
    pass


class DestinationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, min_length=2)
    region: str | None = Field(default=None, min_length=2, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    interests: list[str] | None = None
    season: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class DestinationRead(DestinationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    activities: list[ActivityRead] = Field(default_factory=list)
