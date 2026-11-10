from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import AiRequest, AiService, User
from app.schemas.reports import (
    UsageReportResponse,
    UsageReportRow,
    UsageReportTotals,
)


def usage_report(
    session: Session,
    *,
    user_id: int | None = None,
    service_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> UsageReportResponse:
    conditions = []
    if user_id is not None:
        conditions.append(AiRequest.user_id == user_id)
    if service_id is not None:
        conditions.append(AiRequest.service_id == service_id)
    if date_from is not None:
        conditions.append(AiRequest.created_at >= date_from)
    if date_to is not None:
        conditions.append(AiRequest.created_at <= date_to)

    day = func.date(func.timezone("UTC", AiRequest.created_at)).label("day")
    consumed = AiRequest.status.in_(("ok", "error"))
    stmt = (
        select(
            day,
            AiService.id.label("service_id"),
            AiService.slug.label("service_slug"),
            AiService.name.label("service_name"),
            User.id.label("user_id"),
            User.email.label("user_email"),
            func.count(AiRequest.id).label("requests"),
            func.coalesce(
                func.sum(case((AiRequest.status == "blocked", 1), else_=0)), 0
            ).label("blocked"),
            func.coalesce(
                func.sum(case((consumed, AiRequest.tokens_in), else_=0)), 0
            ).label("tokens_in"),
            func.coalesce(
                func.sum(case((consumed, AiRequest.tokens_out), else_=0)), 0
            ).label("tokens_out"),
        )
        .join(AiService, AiService.id == AiRequest.service_id)
        .join(User, User.id == AiRequest.user_id)
        .group_by(
            day,
            AiService.id,
            AiService.slug,
            AiService.name,
            User.id,
            User.email,
        )
        .order_by(day, AiService.name, User.email)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    rows = [
        UsageReportRow(
            date=str(row.day),
            service_id=row.service_id,
            service_slug=row.service_slug,
            service_name=row.service_name,
            user_id=row.user_id,
            user_email=row.user_email,
            requests=int(row.requests),
            blocked=int(row.blocked),
            tokens_in=int(row.tokens_in),
            tokens_out=int(row.tokens_out),
            tokens_total=int(row.tokens_in) + int(row.tokens_out),
        )
        for row in session.execute(stmt).all()
    ]
    totals = UsageReportTotals(
        requests=sum(row.requests for row in rows),
        blocked=sum(row.blocked for row in rows),
        tokens_in=sum(row.tokens_in for row in rows),
        tokens_out=sum(row.tokens_out for row in rows),
        tokens_total=sum(row.tokens_total for row in rows),
    )
    return UsageReportResponse(
        generated_at=datetime.now(UTC),
        rows=rows,
        totals=totals,
    )
