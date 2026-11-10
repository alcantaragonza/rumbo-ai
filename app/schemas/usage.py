from pydantic import BaseModel, Field


class ServiceUsageRead(BaseModel):
    service_id: int
    service_slug: str
    service_name: str
    requests: int
    blocked: int
    tokens_in: int
    tokens_out: int
    tokens_total: int


class UsageSummaryRead(BaseModel):
    user_id: int | None
    token_limit: int | None
    tokens_used: int
    tokens_remaining: int | None
    requests: int
    blocked: int
    tokens_in: int
    tokens_out: int
    tokens_total: int
    by_service: list[ServiceUsageRead]


class QuotaCheckRequest(BaseModel):
    service_id: int
    estimated_tokens: int = Field(gt=0)


class QuotaCheckResponse(BaseModel):
    ok: bool
    tokens_used: int
    token_limit: int
    tokens_remaining: int
