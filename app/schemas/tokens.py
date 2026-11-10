from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    scope: str = Field(default="read", pattern="^(read|write)$")


class ApiTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)


    id: int
    name: str
    scope: str
    last_used_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None


class ApiTokenCreated(ApiTokenRead):
    token: str
