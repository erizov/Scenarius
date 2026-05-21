"""Wiktionary ingest (proverbs, set phrases)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from scrapers.mediawiki import run_mediawiki_ingest
from scrapers.pull_log import PullLog


def run_wiktionary_ru(
    db: Session,
    *,
    max_pages: int = 150,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest Russian Wiktionary proverb categories."""
    return run_mediawiki_ingest(
        db,
        "wiktionary_ru",
        max_pages=max_pages,
        pull_log=pull_log,
    )
