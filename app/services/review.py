"""Review queue for scraped fragments."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Fragment, FragmentTag, SourceRef

REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"

CURATED_SOURCES = frozenset({"canonical", "seed"})


def is_scraped(fragment: Fragment) -> bool:
    """True when fragment came from a scraper, not canonical seed."""
    if fragment.verified:
        return False
    for source in fragment.sources:
        if source.source_site not in CURATED_SOURCES:
            return True
    status = (fragment.meta or {}).get("review_status")
    return status == REVIEW_PENDING


def list_review_queue(
    db: Session,
    *,
    status: str = REVIEW_PENDING,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Fragment], int]:
    """Return scraped fragments awaiting or in review."""
    status_filter = Fragment.meta["review_status"].as_string() == status
    stmt = (
        select(Fragment)
        .options(
            selectinload(Fragment.work),
            selectinload(Fragment.sources),
            selectinload(Fragment.fragment_tags).selectinload(FragmentTag.tag),
        )
        .where(
            Fragment.verified.is_(False),
            status_filter,
        )
        .order_by(Fragment.created_at.desc())
    )
    count_stmt = select(func.count()).select_from(Fragment).where(
        Fragment.verified.is_(False),
        status_filter,
    )
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return list(rows), total


def count_by_status(db: Session) -> dict[str, int]:
    """Count fragments in each review status."""
    counts = {REVIEW_PENDING: 0, REVIEW_APPROVED: 0, REVIEW_REJECTED: 0}
    rows = db.execute(
        select(
            Fragment.meta["review_status"].as_string(),
            func.count(),
        )
        .where(Fragment.meta["review_status"].isnot(None))
        .group_by(Fragment.meta["review_status"].as_string()),
    ).all()
    for status, total in rows:
        if status in counts:
            counts[status] = total
    return counts


def approve_fragment(db: Session, fragment_id: uuid.UUID) -> Fragment | None:
    """Mark fragment verified and approved for search."""
    fragment = db.get(Fragment, fragment_id)
    if fragment is None:
        return None
    fragment.verified = True
    meta = dict(fragment.meta or {})
    meta["review_status"] = REVIEW_APPROVED
    fragment.meta = meta
    db.commit()
    db.refresh(fragment)
    return fragment


def reject_fragment(db: Session, fragment_id: uuid.UUID) -> Fragment | None:
    """Hide fragment from public search."""
    fragment = db.get(Fragment, fragment_id)
    if fragment is None:
        return None
    meta = dict(fragment.meta or {})
    meta["review_status"] = REVIEW_REJECTED
    fragment.meta = meta
    fragment.verified = False
    db.commit()
    db.refresh(fragment)
    return fragment


def public_visibility_filter():
    """SQLAlchemy filter excluding rejected scraped fragments."""
    status = Fragment.meta["review_status"].as_string()
    return or_(
        Fragment.meta["review_status"].is_(None),
        status != REVIEW_REJECTED,
    )
