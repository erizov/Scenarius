"""Core ingest: upsert fragments with dedup and provenance."""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Fragment,
    FragmentType,
    Person,
    SourceRef,
    Work,
    WorkKind,
)
from app.services.embeddings import upsert_embedding
from app.services.fragments import get_or_create_tag
from app.models import FragmentTag
from scrapers.dedup import text_fingerprint

logger = structlog.get_logger()

BATCH_COMMIT_EVERY = 10
CURATED_SOURCES = frozenset({"canonical", "seed"})


def tier_for_language(language: str, explicit: int | None = None) -> int:
    """RU tier 1; EN and other foreign languages tier 2."""
    if explicit is not None:
        return explicit
    return 1 if language == "ru" else 2


def _review_meta(*, verified: bool, source_site: str) -> dict:
    if verified or source_site in CURATED_SOURCES:
        return {"review_status": "approved"}
    return {"review_status": "pending"}


def maybe_commit_batch(
    db: Session,
    processed: int,
    *,
    every: int = BATCH_COMMIT_EVERY,
    step: str = "ingest",
) -> None:
    """Commit periodically so stats/watch and other sessions see progress."""
    if processed <= 0 or processed % every != 0:
        return
    db.commit()
    logger.info(f"{step}.batch_committed", processed=processed)


def slugify(value: str) -> str:
    """Create a simple ASCII slug from title."""
    import re

    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value, flags=re.UNICODE)
    return value[:120] or "unknown"


def get_or_create_work(
    db: Session,
    *,
    title: str,
    kind: WorkKind,
    language: str,
    tier: int | None = None,
    year: int | None = None,
    external_slug: str | None = None,
) -> Work:
    """Find or create a work by slug derived from title or external id."""
    slug = external_slug or slugify(title)
    resolved_tier = tier_for_language(language, tier)
    work = db.scalars(select(Work).where(Work.slug == slug)).first()
    if work is None:
        work = Work(
            slug=slug,
            title=title,
            kind=kind,
            tier=resolved_tier,
            language=language,
            year=year,
            meta={},
        )
        db.add(work)
        db.flush()
    return work


def get_or_create_speaker(db: Session, name: str) -> Person:
    """Find or create a speaker person."""
    slug = slugify(name)
    person = db.scalars(select(Person).where(Person.slug == slug)).first()
    if person is None:
        person = Person(slug=slug, name=name, meta={"role": "character"})
        db.add(person)
        db.flush()
    return person


def _source_exists(
    db: Session,
    fragment_id: Any,
    source_site: str,
    external_id: str | None,
) -> bool:
    stmt = select(SourceRef).where(
        SourceRef.fragment_id == fragment_id,
        SourceRef.source_site == source_site,
    )
    if external_id:
        stmt = stmt.where(SourceRef.external_id == external_id)
    return db.scalars(stmt).first() is not None


def upsert_fragment(
    db: Session,
    *,
    text: str,
    language: str,
    fragment_type: FragmentType,
    source_site: str,
    source_url: str | None = None,
    external_id: str | None = None,
    license_hint: str | None = None,
    work: Work | None = None,
    speaker_name: str | None = None,
    context: str | None = None,
    tags: list[str] | None = None,
    verified: bool = False,
    embed: bool = True,
) -> tuple[Fragment, bool]:
    """Insert fragment or attach new source to existing duplicate.

    Returns (fragment, created).
    """
    text = text.strip()
    if len(text) < 3:
        raise ValueError("Fragment text too short")

    fp = text_fingerprint(text, language)
    fragment = db.scalars(
        select(Fragment).where(Fragment.text_fingerprint == fp),
    ).first()

    created = fragment is None
    if created:
        speaker = None
        if speaker_name:
            speaker = get_or_create_speaker(db, speaker_name)
        fragment = Fragment(
            work_id=work.id if work else None,
            speaker_id=speaker.id if speaker else None,
            text=text,
            text_fingerprint=fp,
            fragment_type=fragment_type,
            language=language,
            verified=verified,
            context=context,
            meta=_review_meta(verified=verified, source_site=source_site),
        )
        db.add(fragment)
        db.flush()
        if tags:
            for tag_name in tags:
                tag = get_or_create_tag(db, tag_name)
                db.add(FragmentTag(fragment_id=fragment.id, tag_id=tag.id))
    elif work and fragment.work_id is None:
        fragment.work_id = work.id

    if not _source_exists(db, fragment.id, source_site, external_id):
        db.add(
            SourceRef(
                fragment_id=fragment.id,
                source_site=source_site,
                source_url=source_url,
                external_id=external_id,
                license_hint=license_hint,
                scraped_at=datetime.now(tz=UTC),
            ),
        )

    if embed and created:
        upsert_embedding(db, fragment)

    return fragment, created


def ingest_stats(created: int, skipped: int, merged: int) -> dict[str, int]:
    """Return ingest counters."""
    return {
        "created": created,
        "skipped": skipped,
        "merged": merged,
        "total_processed": created + skipped + merged,
    }
