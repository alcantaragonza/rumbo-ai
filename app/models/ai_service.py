from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiService(Base):
    __tablename__ = "ai_services"
    __table_args__ = (
        CheckConstraint("kind IN ('chatbot', 'agent')", name="ck_ai_services_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="chatbot", server_default="chatbot")
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    model: Mapped[str] = mapped_column(
        String(120), default="llama-3.1-8b-instant", server_default="llama-3.1-8b-instant"
    )
    system_prompt: Mapped[str] = mapped_column(Text, default="", server_default="")
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
