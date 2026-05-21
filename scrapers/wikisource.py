"""Wikisource ingest (fairy tales, literature)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from scrapers.mediawiki import run_mediawiki_ingest
from scrapers.pull_log import PullLog


def run_wikisource_ru(
    db: Session,
    *,
    max_pages: int = 200,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest Russian Wikisource categories."""
    return run_mediawiki_ingest(
        db,
        "wikisource_ru",
        max_pages=max_pages,
        pull_log=pull_log,
    )


def run_wikisource_en(
    db: Session,
    *,
    max_pages: int = 100,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest English Wikisource categories (tier 2)."""
    return run_mediawiki_ingest(
        db,
        "wikisource_en",
        max_pages=max_pages,
        pull_log=pull_log,
    )
