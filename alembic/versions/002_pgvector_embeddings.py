"""002 pgvector, fingerprint, embeddings

Revision ID: 002_pgvector
Revises: 001_initial
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_pgvector"
down_revision: Union[str, None] = "001_initial"
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


def upgrade() -> None:
    op.add_column(
        "fragments",
        sa.Column("text_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_fragments_text_fingerprint",
        "fragments",
        ["text_fingerprint"],
        unique=True,
    )

    if not _pgvector_available():
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
    bind = op.get_bind()
    has_table = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'fragment_embeddings'"
            ")"
        ),
    ).scalar()
    if has_table:
        op.execute("DROP INDEX IF EXISTS ix_fragment_embeddings_hnsw")
        op.drop_table("fragment_embeddings")

    op.drop_index("ix_fragments_text_fingerprint", table_name="fragments")
    op.drop_column("fragments", "text_fingerprint")
