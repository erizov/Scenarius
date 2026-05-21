"""Ingest aphorisms and anecdotes from anekdot.ru."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import structlog
import yaml
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models import FragmentType, WorkKind
from scrapers.fail_fast import on_error
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog

logger = structlog.get_logger()

BASE_URL = "https://www.anekdot.ru"
SITE = "anekdot.ru"


def _load_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["anekdot_ru"]


def extract_feed_texts(html: str) -> list[str]:
    """Parse anecdote/aphorism texts from a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    texts: list[str] = []
    for node in soup.select("div.text"):
        raw = node.get_text("\n", strip=True)
        if len(raw) < 18:
            continue
        if raw.lower().startswith("читать дальше"):
            continue
        texts.append(raw)
    return texts


def _feed_url(path: str, page: int) -> str:
    base = path.rstrip("/")
    if page <= 1:
        return urljoin(BASE_URL, base + "/")
    return urljoin(BASE_URL, f"{base}/{page}/")


def _ingest_feed(
    db: Session,
    client: ScraperClient,
    feed: dict[str, Any],
    stats: dict[str, int],
    *,
    max_pages: int,
    pull_log: PullLog | None = None,
) -> None:
    fragment_type = FragmentType(feed.get("fragment_type", "aphorism"))
    language = feed.get("language", "ru")
    work = get_or_create_work(
        db,
        title=feed.get("collection_title", "Anekdot.ru"),
        kind=WorkKind(feed.get("work_kind", "other")),
        language=language,
        tier=feed.get("tier", 2),
        external_slug=f"anekdot-{feed['name']}",
    )

    for page in range(1, max_pages + 1):
        if stats["total_processed"] >= stats["_max"]:
            return

        url = _feed_url(feed["path"], page)
        try:
            response = client.fetch(
                url,
                pull_log=pull_log,
                source="anekdot_ru",
            )
            if response is None:
                stats["pull_skipped"] += 1
                continue
            html = response.text
        except Exception as exc:
            on_error(exc, "anekdot_ru.page_failed", url=url)
            continue

        texts = extract_feed_texts(html)
        if not texts:
            logger.info("anekdot_ru.page_empty", url=url)
            break

        for index, text in enumerate(texts):
            if stats["total_processed"] >= stats["_max"]:
                return
            external_id = f"{feed['name']}:{page}:{index}"
            try:
                _, created = upsert_fragment(
                    db,
                    text=text,
                    language=language,
                    fragment_type=fragment_type,
                    source_site=SITE,
                    source_url=url,
                    external_id=external_id,
                    license_hint="anekdot.ru-user-content",
                    work=work,
                    tags=["anekdot_ru", feed["name"]],
                    embed=False,
                )
            except ValueError:
                stats["skipped"] += 1
                continue

            stats["total_processed"] += 1
            if created:
                stats["created"] += 1
            else:
                stats["merged"] += 1

            processed = stats["created"] + stats["merged"] + stats["skipped"]
            if processed % 10 == 0:
                logger.info(
                    "anekdot_ru.progress",
                    feed=feed["name"],
                    **{k: stats[k] for k in stats if not k.startswith("_")},
                )
            maybe_commit_batch(db, processed, step="anekdot_ru")


def run_anekdot_ru(
    db: Session,
    *,
    max_items: int = 500,
    max_pages: int = 20,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest aphorisms and anecdotes from anekdot.ru feeds."""
    config = _load_config()
    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
        "_max": max_items,
    }
    logger.info(
        "anekdot_ru.ingest_begin",
        max_items=max_items,
        feeds=len(config.get("feeds", [])),
    )

    with ScraperClient() as client:
        for feed in config.get("feeds", []):
            if stats["total_processed"] >= max_items:
                break
            logger.info("anekdot_ru.feed_start", name=feed["name"])
            _ingest_feed(
                db,
                client,
                feed,
                stats,
                max_pages=max_pages,
                pull_log=pull_log,
            )

    db.commit()
    stats.pop("_max", None)
    logger.info("anekdot_ru.ingest_complete", **stats)
    return stats
