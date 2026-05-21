"""Ingest English poetry lines from poetrydb.org."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import structlog
from sqlalchemy.orm import Session

from app.models import FragmentType, WorkKind
from scrapers.fail_fast import on_error
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog
from scrapers.sources import load_source, source_enabled

logger = structlog.get_logger()

SITE = "poetrydb.org"


def _poem_url(api_url: str, author: str, title: str) -> str:
    root = api_url.rstrip("/")
    return (
        f"{root}/author,title/"
        f"{quote(author)};{quote(title)}"
    )


def _normalize_poems(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _poem_lines(
    poem: dict[str, Any],
    *,
    max_lines: int,
) -> list[str]:
    lines = poem.get("lines") or []
    title = str(poem.get("title") or "Untitled")
    author = poem.get("author")
    if isinstance(author, list):
        author = author[0] if author else "Unknown"
    author = str(author or "Unknown")

    out: list[str] = []
    for line in lines[:max_lines]:
        text = str(line).strip()
        if len(text) < 12:
            continue
        out.append(text)
    if not out and title:
        out.append(f"{title} — {author}")
    return out


def run_poetrydb(
    db: Session,
    *,
    max_items: int = 2500,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest poem lines from poetrydb.org for configured poems."""
    if not source_enabled("poetrydb"):
        logger.info("poetrydb.skipped", reason="disabled")
        return {
            "created": 0,
            "merged": 0,
            "skipped": 0,
            "pull_skipped": 0,
            "total_processed": 0,
        }

    config = load_source("poetrydb")
    api_url = config.get("api_url", "https://poetrydb.org")
    poems = config.get("poems") or []
    max_lines = int(config.get("max_lines_per_poem", 24))
    language = config.get("language", "en")
    tier = int(config.get("tier", 2))
    license_hint = config.get("license_hint", "poetrydb.org")

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info(
        "poetrydb.ingest_begin",
        max_items=max_items,
        poems=len(poems),
    )

    with ScraperClient() as client:
        for poem_cfg in poems:
            if stats["total_processed"] >= max_items:
                break
            author = str(poem_cfg.get("author") or "")
            title = str(poem_cfg.get("title") or "")
            if not author or not title:
                stats["skipped"] += 1
                continue
            url = _poem_url(api_url, author, title)
            try:
                payload = client.get_json(
                    url,
                    pull_log=pull_log,
                    source="poetrydb",
                )
            except Exception as exc:
                on_error(
                    exc,
                    "poetrydb.poem_failed",
                    author=author,
                    title=title,
                    url=url,
                )
                continue
            if payload is None:
                stats["pull_skipped"] += 1
                continue

            for poem in _normalize_poems(payload):
                if stats["total_processed"] >= max_items:
                    break
                poem_title = str(poem.get("title") or title)
                work = get_or_create_work(
                    db,
                    title=poem_title,
                    kind=WorkKind.poem,
                    language=language,
                    tier=tier,
                    external_slug=f"poetrydb-{author}-{poem_title}"[:120],
                )
                for line in _poem_lines(poem, max_lines=max_lines):
                    if stats["total_processed"] >= max_items:
                        break
                    external_id = f"{author}:{poem_title}:{line[:40]}"
                    try:
                        _, created = upsert_fragment(
                            db,
                            text=line,
                            language=language,
                            fragment_type=FragmentType.quote,
                            source_site=SITE,
                            source_url=url,
                            external_id=external_id,
                            license_hint=license_hint,
                            work=work,
                            context=author,
                            tags=["poetrydb"],
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
                        step="poetrydb",
                    )

    db.commit()
    logger.info("poetrydb.ingest_complete", **stats)
    return stats
