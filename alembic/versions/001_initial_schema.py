"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

work_kind = postgresql.ENUM(
    "film",
    "book",
    "poem",
    "cartoon",
    "fairy_tale",
    "proverb_collection",
    "song",
    "other",
    name="workkind",
    create_type=False,
)
fragment_type = postgresql.ENUM(
    "quote",
    "dialogue",
    "aphorism",
    "proverb",
    "phraseologism",
    "fairy_formula",
    "slang",
    "song_lyric",
    name="fragmenttype",
    create_type=False,
)
person_role = postgresql.ENUM(
    "author",
    "director",
    "speaker",
    "composer",
    "collector",
    name="personrole",
    create_type=False,
)


def _ensure_enums() -> None:
    """Create PostgreSQL ENUM types idempotently."""
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE workkind AS ENUM (
                'film', 'book', 'poem', 'cartoon', 'fairy_tale',
                'proverb_collection', 'song', 'other'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE fragmenttype AS ENUM (
                'quote', 'dialogue', 'aphorism', 'proverb',
                'phraseologism', 'fairy_formula', 'slang', 'song_lyric'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE personrole AS ENUM (
                'author', 'director', 'speaker', 'composer', 'collector'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    _ensure_enums()

    op.create_table(
        "works",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("kind", work_kind, nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_works_kind", "works", ["kind"])
    op.create_index("ix_works_language", "works", ["language"])
    op.create_index("ix_works_tier", "works", ["tier"])

    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_people_name", "people", ["name"])

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_tags_name", "tags", ["name"])

    op.create_table(
        "work_people",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", person_role, nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "person_id", "role", name="uq_work_person"),
    )
    op.create_index("ix_work_people_person_id", "work_people", ["person_id"])
    op.create_index("ix_work_people_work_id", "work_people", ["work_id"])

    op.create_table(
        "fragments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("speaker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("fragment_type", fragment_type, nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["speaker_id"], ["people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fragments_fragment_type", "fragments", ["fragment_type"])
    op.create_index("ix_fragments_language", "fragments", ["language"])
    op.create_index("ix_fragments_speaker_id", "fragments", ["speaker_id"])
    op.create_index("ix_fragments_verified", "fragments", ["verified"])
    op.create_index("ix_fragments_work_id", "fragments", ["work_id"])

    op.create_table(
        "fragment_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fragment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["fragment_id"], ["fragments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fragment_id", "tag_id", name="uq_fragment_tag"),
    )
    op.create_index("ix_fragment_tags_fragment_id", "fragment_tags", ["fragment_id"])
    op.create_index("ix_fragment_tags_tag_id", "fragment_tags", ["tag_id"])

    op.create_table(
        "source_refs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fragment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_site", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("license_hint", sa.String(length=255), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["fragment_id"],
            ["fragments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_refs_fragment_id", "source_refs", ["fragment_id"])


def downgrade() -> None:
    op.drop_index("ix_source_refs_fragment_id", table_name="source_refs")
    op.drop_table("source_refs")
    op.drop_index("ix_fragment_tags_tag_id", table_name="fragment_tags")
    op.drop_index("ix_fragment_tags_fragment_id", table_name="fragment_tags")
    op.drop_table("fragment_tags")
    op.drop_index("ix_fragments_work_id", table_name="fragments")
    op.drop_index("ix_fragments_verified", table_name="fragments")
    op.drop_index("ix_fragments_speaker_id", table_name="fragments")
    op.drop_index("ix_fragments_language", table_name="fragments")
    op.drop_index("ix_fragments_fragment_type", table_name="fragments")
    op.drop_table("fragments")
    op.drop_index("ix_work_people_work_id", table_name="work_people")
    op.drop_index("ix_work_people_person_id", table_name="work_people")
    op.drop_table("work_people")
    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_people_name", table_name="people")
    op.drop_table("people")
    op.drop_index("ix_works_tier", table_name="works")
    op.drop_index("ix_works_language", table_name="works")
    op.drop_index("ix_works_kind", table_name="works")
    op.drop_table("works")

    person_role.drop(op.get_bind(), checkfirst=True)
    fragment_type.drop(op.get_bind(), checkfirst=True)
    work_kind.drop(op.get_bind(), checkfirst=True)
