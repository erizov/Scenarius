"""003 ensure fragment_embeddings when pgvector added later

Revision ID: 003_embeddings
Revises: 002_pgvector
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_embeddings"
down_revision: Union[str, None] = "002_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pgvector_available() -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_available_extensions "
                "WHERE name = 'vector'"
                ")"
            ),
        ).scalar(),
    )


def _table_exists() -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                "SELECT to_regclass('public.fragment_embeddings') IS NOT NULL"
            ),
        ).scalar(),
    )


def upgrade() -> None:
    if not _pgvector_available():
        return
    if _table_exists():
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE fragment_embeddings (
            fragment_id UUID PRIMARY KEY
                REFERENCES fragments(id) ON DELETE CASCADE,
            embedding vector(384) NOT NULL,
            model_name VARCHAR(120) NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_fragment_embeddings_hnsw "
        "ON fragment_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    if not _table_exists():
        return
    op.execute("DROP INDEX IF EXISTS ix_fragment_embeddings_hnsw")
    op.drop_table("fragment_embeddings")
