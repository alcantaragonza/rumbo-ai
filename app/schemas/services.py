from pydantic import BaseModel, ConfigDict


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    kind: str
    is_enabled: bool
    model: str
