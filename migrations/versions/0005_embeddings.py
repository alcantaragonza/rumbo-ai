"""Embeddings para búsqueda semántica con pgvector.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "destinations", sa.Column("embedding", Vector(384), nullable=True)
    )
    op.add_column("activities", sa.Column("embedding", Vector(384), nullable=True))
    op.execute(
        "CREATE INDEX ix_destinations_embedding ON destinations "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_activities_embedding ON activities "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_activities_embedding", table_name="activities")
    op.drop_index("ix_destinations_embedding", table_name="destinations")
    op.drop_column("activities", "embedding")
    op.drop_column("destinations", "embedding")
