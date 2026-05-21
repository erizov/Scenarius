"""Ingest English aphorisms from quotable.io."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models import FragmentType, WorkKind
from scrapers.fail_fast import on_error
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog
from scrapers.sources import load_source, source_enabled

logger = structlog.get_logger()

SITE = "quotable.io"


def run_quotable(
    db: Session,
    *,
    max_items: int = 800,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest quotes from quotable.io (paginated /quotes)."""
    if not source_enabled("quotable"):
        logger.info("quotable.skipped", reason="disabled")
        return {
            "created": 0,
            "merged": 0,
            "skipped": 0,
            "pull_skipped": 0,
            "total_processed": 0,
        }

    config = load_source("quotable")
    api_url = config.get("api_url", "https://api.quotable.io")
    page_size = int(config.get("page_size", 150))
    language = config.get("language", "en")
    tier = int(config.get("tier", 2))
    license_hint = config.get("license_hint", "quotable.io")

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info("quotable.ingest_begin", max_items=max_items)

    work = get_or_create_work(
        db,
        title="Quotable.io",
        kind=WorkKind.other,
        language=language,
        tier=tier,
        external_slug="quotable-io",
    )

    page = 1
    with ScraperClient() as client:
        while stats["total_processed"] < max_items:
            url = f"{api_url.rstrip('/')}/quotes"
            params: dict[str, Any] = {
                "limit": min(page_size, max_items - stats["total_processed"]),
                "page": page,
            }
            try:
                payload = client.get_json(
                    url,
                    params=params,
                    pull_log=pull_log,
                    source="quotable",
                )
            except Exception as exc:
                on_error(exc, "quotable.page_failed", page=page, url=url)
                break
            if payload is None:
                stats["pull_skipped"] += 1
                break

            results = payload.get("results") or []
            if not results:
                break

            for quote in results:
                if stats["total_processed"] >= max_items:
                    break
                text = str(quote.get("content") or "").strip()
                if len(text) < 12:
                    stats["skipped"] += 1
                    continue
                author = str(quote.get("author") or "Unknown")
                quote_id = str(quote.get("_id") or quote.get("id") or text[:40])
                source_url = f"{api_url.rstrip('/')}/quotes/{quote_id}"
                try:
                    _, created = upsert_fragment(
                        db,
                        text=text,
                        language=language,
                        fragment_type=FragmentType.aphorism,
                        source_site=SITE,
                        source_url=source_url,
                        external_id=quote_id,
                        license_hint=license_hint,
                        work=work,
                        speaker_name=author,
                        tags=["quotable"],
                    )
                except ValueError:
                    stats["skipped"] += 1
                    continue

                stats["total_processed"] += 1
                if created:
                    stats["created"] += 1
                else:
                    stats["merged"] += 1
                maybe_commit_batch(
                    db,
                    stats["total_processed"],
                    step="quotable",
                )

            if not payload.get("nextPage"):
                break
            page += 1

    db.commit()
    logger.info("quotable.ingest_complete", **stats)
    return stats
