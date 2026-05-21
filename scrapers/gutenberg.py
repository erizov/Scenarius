"""Ingest public-domain book passages from Project Gutenberg."""

from __future__ import annotations

import re
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

SITE = "gutenberg.org"
START_RE = re.compile(r"\*\*\* START OF .+?\*\*\*", re.IGNORECASE)
END_RE = re.compile(r"\*\*\* END OF .+?\*\*\*", re.IGNORECASE)


def extract_gutenberg_passages(
    text: str,
    *,
    limit: int = 400,
    min_len: int = 24,
    max_len: int = 420,
) -> list[str]:
    """Extract readable paragraphs from a Gutenberg plain-text file."""
    start = START_RE.search(text)
    end = END_RE.search(text)
    body = text
    if start:
        body = text[start.end():]
    if end:
        body = body[: end.start()]

    passages: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        paragraph = " ".join(block.split())
        if len(paragraph) < min_len:
            continue
        if len(paragraph) > max_len:
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
                sentence = sentence.strip()
                if min_len <= len(sentence) <= max_len:
                    passages.append(sentence)
                if len(passages) >= limit:
                    return passages
            continue
        passages.append(paragraph)
        if len(passages) >= limit:
            break
    return passages


def _book_url(base_url: str, book_id: int) -> str:
    root = base_url.rstrip("/")
    return f"{root}/cache/epub/{book_id}/pg{book_id}.txt"


def run_gutenberg(
    db: Session,
    *,
    max_items: int = 2000,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest passages from configured Gutenberg book IDs."""
    if not source_enabled("gutenberg"):
        logger.info("gutenberg.skipped", reason="disabled")
        return {
            "created": 0,
            "merged": 0,
            "skipped": 0,
            "pull_skipped": 0,
            "total_processed": 0,
        }

    config = load_source("gutenberg")
    base_url = config.get("base_url", "https://www.gutenberg.org")
    books = config.get("books") or []
    per_book = int(config.get("max_passages_per_book", 120))
    license_hint = config.get("license_hint", "public-domain")

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info(
        "gutenberg.ingest_begin",
        max_items=max_items,
        books=len(books),
    )

    with ScraperClient(delay=0.5) as client:
        for book in books:
            if stats["total_processed"] >= max_items:
                break
            book_id = int(book["id"])
            title = str(book.get("title") or f"Gutenberg {book_id}")
            author = str(book.get("author") or "Unknown")
            language = book.get("language", "en")
            tier = int(book.get("tier", 2))
            url = _book_url(base_url, book_id)

            try:
                response = client.fetch(
                    url,
                    pull_log=pull_log,
                    source="gutenberg",
                    timeout=90.0,
                )
            except Exception as exc:
                on_error(
                    exc,
                    "gutenberg.book_failed",
                    book_id=book_id,
                    url=url,
                )
                continue
            if response is None:
                stats["pull_skipped"] += 1
                continue

            passages = extract_gutenberg_passages(
                response.text,
                limit=per_book,
            )
            if not passages:
                stats["skipped"] += 1
                continue

            work = get_or_create_work(
                db,
                title=title,
                kind=WorkKind(book.get("work_kind", "book")),
                language=language,
                tier=tier,
                external_slug=f"gutenberg-{book_id}",
            )
            for index, passage in enumerate(passages):
                if stats["total_processed"] >= max_items:
                    break
                external_id = f"{book_id}:{index}"
                try:
                    _, created = upsert_fragment(
                        db,
                        text=passage,
                        language=language,
                        fragment_type=FragmentType(
                            book.get("fragment_type", "quote"),
                        ),
                        source_site=SITE,
                        source_url=url,
                        external_id=external_id,
                        license_hint=license_hint,
                        work=work,
                        context=author,
                        tags=["gutenberg"],
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
                    step="gutenberg",
                )

    db.commit()
    logger.info("gutenberg.ingest_complete", **stats)
    return stats
