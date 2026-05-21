"""Ingest movie dialogue lines from OpenSubtitles API."""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FragmentType, WorkKind
from scrapers.errors import IngestConfigError
from scrapers.fail_fast import on_error
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog
from scrapers.sources import load_source, require_env, source_enabled
from scrapers.srt_parse import extract_srt_lines

logger = structlog.get_logger()

SITE = "opensubtitles.com"


def _client_headers() -> dict[str, str]:
    api_key = require_env(
        settings.opensubtitles_api_key,
        name="OPENSUBTITLES_API_KEY",
        source=SITE,
    )
    return {
        "Api-Key": api_key,
        "User-Agent": settings.scraper_user_agent,
        "Content-Type": "application/json",
    }


def _search_subtitles(
    client: ScraperClient,
    api_url: str,
    query: str,
    *,
    pull_log: PullLog | None,
    headers: dict[str, str],
) -> list[dict[str, Any]]:
    url = f"{api_url.rstrip('/')}/subtitles"
    payload = client.get_json(
        url,
        params={"query": query},
        pull_log=pull_log,
        source="opensubtitles",
        headers=headers,
    )
    if payload is None:
        return []
    data = payload.get("data") or []
    return data if isinstance(data, list) else []


def _download_subtitle(
    client: ScraperClient,
    api_url: str,
    file_id: int,
    *,
    pull_log: PullLog | None,
    headers: dict[str, str],
) -> str | None:
    url = f"{api_url.rstrip('/')}/download"
    payload = client.post_json(
        url,
        json={"file_id": file_id},
        pull_log=pull_log,
        source="opensubtitles",
        headers=headers,
    )
    if payload is None:
        return None
    link = payload.get("link")
    if not link:
        return None
    file_response = client.fetch(
        str(link),
        pull_log=pull_log,
        source="opensubtitles",
        headers=headers,
    )
    if file_response is None:
        return None
    return file_response.text


def run_opensubtitles(
    db: Session,
    *,
    max_items: int = 1500,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest subtitle dialogue lines via api.opensubtitles.com."""
    if not source_enabled("opensubtitles"):
        logger.info("opensubtitles.skipped", reason="disabled")
        return {
            "created": 0,
            "merged": 0,
            "skipped": 0,
            "pull_skipped": 0,
            "total_processed": 0,
        }

    if not settings.opensubtitles_api_key:
        raise IngestConfigError(
            "OPENSUBTITLES_API_KEY is required for opensubtitles "
            "(set in .env or disable the source)",
        )

    config = load_source("opensubtitles")
    api_url = config.get("api_url", "https://api.opensubtitles.com/api/v1")
    queries = config.get("queries") or []
    max_files = int(config.get("max_files_per_query", 3))
    language = config.get("language", "en")
    tier = int(config.get("tier", 2))
    license_hint = config.get("license_hint", "opensubtitles-user-content")
    headers = _client_headers()

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info(
        "opensubtitles.ingest_begin",
        max_items=max_items,
        queries=len(queries),
    )

    with ScraperClient() as client:
        client._client.headers.update(headers)
        for query_cfg in queries:
            if stats["total_processed"] >= max_items:
                break
            query = str(query_cfg.get("query") or query_cfg.get("title") or "")
            if not query:
                continue
            title = str(query_cfg.get("title") or query)
            work = get_or_create_work(
                db,
                title=title,
                kind=WorkKind(query_cfg.get("work_kind", "film")),
                language=language,
                tier=tier,
                external_slug=f"opensubtitles-{title}"[:120],
            )
            try:
                results = _search_subtitles(
                    client,
                    api_url,
                    query,
                    pull_log=pull_log,
                    headers=headers,
                )
            except Exception as exc:
                on_error(
                    exc,
                    "opensubtitles.search_failed",
                    query=query,
                )
                continue

            for item in results[:max_files]:
                if stats["total_processed"] >= max_items:
                    break
                attrs = item.get("attributes") or {}
                file_id = attrs.get("files", [{}])[0].get("file_id")
                if not file_id:
                    stats["skipped"] += 1
                    continue
                try:
                    srt_text = _download_subtitle(
                        client,
                        api_url,
                        int(file_id),
                        pull_log=pull_log,
                        headers=headers,
                    )
                except Exception as exc:
                    on_error(
                        exc,
                        "opensubtitles.download_failed",
                        file_id=file_id,
                    )
                    continue
                if not srt_text:
                    stats["pull_skipped"] += 1
                    continue

                for index, line in enumerate(extract_srt_lines(srt_text)):
                    if stats["total_processed"] >= max_items:
                        break
                    external_id = f"{file_id}:{index}"
                    try:
                        _, created = upsert_fragment(
                            db,
                            text=line,
                            language=language,
                            fragment_type=FragmentType.dialogue,
                            source_site=SITE,
                            source_url=json.dumps({"file_id": file_id}),
                            external_id=external_id,
                            license_hint=license_hint,
                            work=work,
                            tags=["opensubtitles"],
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
                    maybe_commit_batch(
                        db,
                        stats["total_processed"],
                        step="opensubtitles",
                    )

    db.commit()
    logger.info("opensubtitles.ingest_complete", **stats)
    return stats
