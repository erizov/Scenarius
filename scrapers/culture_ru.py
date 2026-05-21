"""Ingest quotes and literary fragments from culture.ru API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml
from sqlalchemy.orm import Session

from app.models import FragmentType, WorkKind
from scrapers.culture_ru_parse import (
    extract_em_quotes,
    json_text_paragraphs,
    split_poem_stanzas,
    strip_html,
)
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog

logger = structlog.get_logger()

API_URL = "https://www.culture.ru/api"
SITE = "culture.ru"


def _load_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["culture_ru"]


def _api_get(
    client: ScraperClient,
    resource: str,
    *,
    params: dict[str, Any] | None = None,
    pull_log: PullLog | None = None,
) -> dict[str, Any] | None:
    query = params or {}
    url = f"{API_URL}/{resource}"
    return client.get_json(
        url,
        params=query,
        pull_log=pull_log,
        source="culture_ru",
    )


def _list_pages(
    client: ScraperClient,
    resource: str,
    *,
    limit: int,
    max_pages: int,
    extra: dict[str, Any] | None = None,
    pull_log: PullLog | None = None,
    stats: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {"limit": limit, "page": page}
        if extra:
            params.update(extra)
        payload = _api_get(client, resource, params=params, pull_log=pull_log)
        if payload is None:
            if stats is not None:
                stats["pull_skipped"] += 1
            continue
        batch = payload.get("items") or []
        if not batch:
            break
        items.extend(batch)
    return items


def _ingest_texts(
    db: Session,
    *,
    texts: list[str],
    work,
    section: dict[str, Any],
    source_url: str,
    external_prefix: str,
    stats: dict[str, int],
    fragment_type: FragmentType | None = None,
) -> None:
    ftype = fragment_type or FragmentType(section.get("fragment_type", "quote"))
    language = section.get("language", "ru")
    for index, text in enumerate(texts):
        if stats["total_processed"] >= stats.get("_max", 0):
            return
        try:
            _, created = upsert_fragment(
                db,
                text=text,
                language=language,
                fragment_type=ftype,
                source_site=SITE,
                source_url=source_url,
                external_id=f"{external_prefix}:{index}",
                license_hint="culture.ru-attribution",
                work=work,
                tags=["culture_ru", section["resource"]],
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
            logger.info("culture_ru.progress", resource=section["resource"], **stats)
        maybe_commit_batch(db, processed, step="culture_ru")


def _ingest_poems(
    db: Session,
    client: ScraperClient,
    section: dict[str, Any],
    stats: dict[str, int],
    *,
    limit: int,
    max_pages: int,
    pull_log: PullLog | None = None,
) -> None:
    resource = section["resource"]
    items = _list_pages(
        client,
        resource,
        limit=limit,
        max_pages=max_pages,
        pull_log=pull_log,
        stats=stats,
    )
    work_kind = WorkKind(section.get("work_kind", "poem"))
    default_ftype = FragmentType(section.get("fragment_type", "quote"))
    for item in items:
        if stats["total_processed"] >= stats["_max"]:
            break
        item_id = item["_id"]
        detail = _api_get(client, f"{resource}/{item_id}", pull_log=pull_log)
        if detail is None:
            stats["pull_skipped"] += 1
            continue
        text = strip_html(detail.get("text") or "")
        if len(text) < 15:
            stats["skipped"] += 1
            continue

        work = get_or_create_work(
            db,
            title=detail.get("title") or item.get("title") or f"{resource} {item_id}",
            kind=work_kind,
            language=section.get("language", "ru"),
            tier=section.get("tier", 1),
            external_slug=f"culture-{resource}-{item_id}",
        )
        url = f"https://www.culture.ru/{resource}/{item_id}"
        chunks = split_poem_stanzas(text)
        _ingest_texts(
            db,
            texts=chunks[:5],
            work=work,
            section=section,
            source_url=url,
            external_prefix=str(item_id),
            stats=stats,
            fragment_type=default_ftype,
        )


def _ingest_books(
    db: Session,
    client: ScraperClient,
    section: dict[str, Any],
    stats: dict[str, int],
    *,
    limit: int,
    max_pages: int,
    pull_log: PullLog | None = None,
) -> None:
    items = _list_pages(
        client,
        "books",
        limit=limit,
        max_pages=max_pages,
        pull_log=pull_log,
        stats=stats,
    )
    for item in items:
        if stats["total_processed"] >= stats["_max"]:
            break
        book_id = item["_id"]
        detail = _api_get(client, f"books/{book_id}", pull_log=pull_log)
        if detail is None:
            stats["pull_skipped"] += 1
            continue
        paragraphs = json_text_paragraphs(detail.get("jsonText", []))
        annotation = strip_html(detail.get("annotation") or "")
        if annotation and len(annotation) >= 25:
            paragraphs.insert(0, annotation)

        if not paragraphs:
            stats["skipped"] += 1
            continue

        work = get_or_create_work(
            db,
            title=detail.get("title") or item.get("title") or f"Book {book_id}",
            kind=WorkKind.book,
            language=section.get("language", "ru"),
            tier=section.get("tier", 1),
            year=detail.get("year"),
            external_slug=f"culture-book-{book_id}",
        )
        slug = detail.get("name") or book_id
        url = f"https://www.culture.ru/books/{book_id}/{slug}"
        _ingest_texts(
            db,
            texts=paragraphs[:8],
            work=work,
            section=section,
            source_url=url,
            external_prefix=str(book_id),
            stats=stats,
            fragment_type=FragmentType.quote,
        )


def _ingest_movies(
    db: Session,
    client: ScraperClient,
    section: dict[str, Any],
    stats: dict[str, int],
    *,
    limit: int,
    max_pages: int,
    pull_log: PullLog | None = None,
) -> None:
    extra = {}
    if section.get("types"):
        extra["types"] = section["types"]

    items = _list_pages(
        client,
        "movies",
        limit=limit,
        max_pages=max_pages,
        extra=extra,
        pull_log=pull_log,
        stats=stats,
    )
    for item in items:
        if stats["total_processed"] >= stats["_max"]:
            break
        movie_id = item["_id"]
        detail = _api_get(client, f"movies/{movie_id}", pull_log=pull_log)
        if detail is None:
            stats["pull_skipped"] += 1
            continue
        texts: list[str] = []

        for part in detail.get("jsonText") or []:
            if part.get("type") != "text":
                continue
            raw = part.get("text") or ""
            texts.extend(extract_em_quotes(raw))
            clean = strip_html(raw)
            if 25 <= len(clean) <= 280 and "—" in clean:
                texts.append(clean)

        short = strip_html(detail.get("shortText") or "")
        if 25 <= len(short) <= 280:
            texts.insert(0, short)

        deduped: list[str] = []
        seen: set[str] = set()
        for text in texts:
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)

        if not deduped:
            stats["skipped"] += 1
            continue

        work = get_or_create_work(
            db,
            title=detail.get("title") or item.get("title") or f"Movie {movie_id}",
            kind=WorkKind(section.get("work_kind", "film")),
            language=section.get("language", "ru"),
            tier=section.get("tier", 1),
            year=detail.get("year"),
            external_slug=f"culture-movie-{movie_id}",
        )
        slug = detail.get("name") or movie_id
        url = f"https://www.culture.ru/cinema/movies/{slug}/{movie_id}"
        _ingest_texts(
            db,
            texts=deduped[:6],
            work=work,
            section=section,
            source_url=url,
            external_prefix=str(movie_id),
            stats=stats,
            fragment_type=FragmentType.quote,
        )


RESOURCE_HANDLERS = {
    "poems": _ingest_poems,
    "books": _ingest_books,
    "movies": _ingest_movies,
    "musicalCompositions": _ingest_poems,
    "songs": _ingest_poems,
}


def run_culture_ru(
    db: Session,
    *,
    max_items: int = 500,
    page_limit: int = 50,
    max_pages: int = 10,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest literary fragments from culture.ru API."""
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
        "culture_ru.ingest_begin",
        max_items=max_items,
        sections=len(config.get("sections", [])),
    )

    with ScraperClient() as client:
        for section in config.get("sections", []):
            if stats["total_processed"] >= max_items:
                break
            resource = section["resource"]
            handler = RESOURCE_HANDLERS.get(resource)
            if handler is None:
                logger.warning("culture_ru.unknown_resource", resource=resource)
                continue

            logger.info("culture_ru.section_start", resource=resource)
            handler(
                db,
                client,
                section,
                stats,
                limit=page_limit,
                max_pages=max_pages,
                pull_log=pull_log,
            )

    db.commit()
    stats.pop("_max", None)
    logger.info("culture_ru.ingest_complete", **stats)
    return stats
