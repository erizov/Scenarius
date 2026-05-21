import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.base import Base


class WorkKind(str, enum.Enum):
    """Type of creative work."""

    film = "film"
    book = "book"
    poem = "poem"
    cartoon = "cartoon"
    fairy_tale = "fairy_tale"
    proverb_collection = "proverb_collection"
    song = "song"
    other = "other"


class FragmentType(str, enum.Enum):
    """Type of text fragment."""

    quote = "quote"
    dialogue = "dialogue"
    aphorism = "aphorism"
    proverb = "proverb"
    phraseologism = "phraseologism"
    fairy_formula = "fairy_formula"
    slang = "slang"
    song_lyric = "song_lyric"


class PersonRole(str, enum.Enum):
    """Role of a person relative to a work."""

    author = "author"
    director = "director"
    speaker = "speaker"
    composer = "composer"
    collector = "collector"


class Work(Base):
    """Film, book, cartoon, fairy tale, or other source work."""

    __tablename__ = "works"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    kind: Mapped[WorkKind] = mapped_column(Enum(WorkKind), index=True)
    tier: Mapped[int] = mapped_column(Integer, default=1, index=True)
    language: Mapped[str] = mapped_column(String(8), index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    fragments: Mapped[list["Fragment"]] = relationship(
        back_populates="work",
    )
    work_people: Mapped[list["WorkPerson"]] = relationship(
        back_populates="work",
    )


class Person(Base):
    """Author, director, character speaker, or collector."""

    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str | None] = mapped_column(
        String(120),
        unique=True,
        nullable=True,
    )
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    work_people: Mapped[list["WorkPerson"]] = relationship(
        back_populates="person",
    )
    spoken_fragments: Mapped[list["Fragment"]] = relationship(
        back_populates="speaker",
        foreign_keys="Fragment.speaker_id",
    )


class WorkPerson(Base):
    """Many-to-many link between works and people with a role."""

    __tablename__ = "work_people"
    __table_args__ = (
        UniqueConstraint("work_id", "person_id", "role", name="uq_work_person"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"),
        index=True,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[PersonRole] = mapped_column(Enum(PersonRole))

    work: Mapped["Work"] = relationship(back_populates="work_people")
    person: Mapped["Person"] = relationship(back_populates="work_people")


class Tag(Base):
    """Free-form tag for fragments."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    fragment_tags: Mapped[list["FragmentTag"]] = relationship(
        back_populates="tag",
    )


class Fragment(Base):
    """Quote, dialogue, proverb, or other text unit."""

    __tablename__ = "fragments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    work_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("works.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    speaker_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text)
    text_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )
    fragment_type: Mapped[FragmentType] = mapped_column(
        Enum(FragmentType),
        index=True,
    )
    language: Mapped[str] = mapped_column(String(8), index=True)
    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    work: Mapped["Work | None"] = relationship(back_populates="fragments")
    speaker: Mapped["Person | None"] = relationship(
        back_populates="spoken_fragments",
        foreign_keys=[speaker_id],
    )
    fragment_tags: Mapped[list["FragmentTag"]] = relationship(
        back_populates="fragment",
    )
    sources: Mapped[list["SourceRef"]] = relationship(
        back_populates="fragment",
    )
    embedding: Mapped["FragmentEmbedding | None"] = relationship(
        back_populates="fragment",
        uselist=False,
    )


class FragmentEmbedding(Base):
    """Vector embedding for semantic search."""

    __tablename__ = "fragment_embeddings"

    fragment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fragments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    model_name: Mapped[str] = mapped_column(String(120))

    fragment: Mapped["Fragment"] = relationship(back_populates="embedding")


class FragmentTag(Base):
    """Many-to-many link between fragments and tags."""

    __tablename__ = "fragment_tags"
    __table_args__ = (
        UniqueConstraint("fragment_id", "tag_id", name="uq_fragment_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    fragment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fragments.id", ondelete="CASCADE"),
        index=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        index=True,
    )

    fragment: Mapped["Fragment"] = relationship(back_populates="fragment_tags")
    tag: Mapped["Tag"] = relationship(back_populates="fragment_tags")


class SourceRef(Base):
    """Provenance for a fragment (where it was collected from)."""

    __tablename__ = "source_refs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    fragment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fragments.id", ondelete="CASCADE"),
        index=True,
    )
    source_site: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    fragment: Mapped["Fragment"] = relationship(back_populates="sources")
