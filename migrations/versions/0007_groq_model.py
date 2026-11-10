"""Actualizar el modelo por defecto de Groq.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE ai_services SET model = 'openai/gpt-oss-20b' "
        "WHERE model = 'llama-3.1-8b-instant'"
    )
    op.alter_column(
        "ai_services",
        "model",
        existing_type=sa.String(length=120),
        server_default="openai/gpt-oss-20b",
    )


def downgrade() -> None:
    op.alter_column(
        "ai_services",
        "model",
        existing_type=sa.String(length=120),
        server_default="llama-3.1-8b-instant",
    )
    op.execute(
        "UPDATE ai_services SET model = 'llama-3.1-8b-instant' "
        "WHERE model = 'openai/gpt-oss-20b'"
    )
