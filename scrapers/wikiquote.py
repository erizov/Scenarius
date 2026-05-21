"""Wikiquote ingest via shared MediaWiki runner."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from scrapers.mediawiki import run_mediawiki_ingest
from scrapers.pull_log import PullLog


def run_wikiquote(
    db: Session,
    lang: str,
    *,
    max_pages: int = 150,
    max_quotes_per_page: int = 40,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest quotes from ru/en Wikiquote categories."""
    return run_mediawiki_ingest(
        db,
        f"wikiquote_{lang}",
        max_pages=max_pages,
        max_items_per_page=max_quotes_per_page,
        pull_log=pull_log,
    )


def run_wikiquote_ru(db: Session, **kwargs: Any) -> dict[str, int]:
    """Ingest Russian Wikiquote."""
    return run_wikiquote(db, "ru", **kwargs)


def run_wikiquote_en(db: Session, **kwargs: Any) -> dict[str, int]:
    """Ingest English Wikiquote."""
    return run_wikiquote(db, "en", **kwargs)
