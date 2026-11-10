from datetime import datetime

from pydantic import BaseModel


class UsageReportRow(BaseModel):
    date: str
    service_id: int
    service_slug: str
    service_name: str
    user_id: int
    user_email: str
    requests: int
    blocked: int
    tokens_in: int
    tokens_out: int
    tokens_total: int


class UsageReportTotals(BaseModel):
    requests: int
    blocked: int
    tokens_in: int
    tokens_out: int
    tokens_total: int


class UsageReportResponse(BaseModel):
    timezone: str = "UTC"
    currency: str = "USD"
    generated_at: datetime
    rows: list[UsageReportRow]
    totals: UsageReportTotals
