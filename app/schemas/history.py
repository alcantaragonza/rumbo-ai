from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: list[dict[str, Any]]
    tokens_in: int
    tokens_out: int
    created_at: datetime


class ConversationSummary(BaseModel):
    id: int
    title: str
    service_id: int
    service_slug: str
    service_name: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    tokens_total: int


class ConversationRead(BaseModel):
    id: int
    title: str
    service_id: int
    service_slug: str
    service_name: str
    created_at: datetime
    updated_at: datetime
    tokens_total: int
    messages: list[MessageRead]
