from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    service_slug: str = Field(default="chatbot", min_length=2, max_length=60)


class ChatResponse(BaseModel):
    conversation_id: int
    message: str
    sources: list[dict[str, Any]]
    tokens_in: int
    tokens_out: int
    tokens_total: int
    tokens_remaining: int
    insufficient_context: bool
