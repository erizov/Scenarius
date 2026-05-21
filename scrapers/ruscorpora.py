"""Ingest Russian poetry lines from the National Corpus (НКРЯ) API."""

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

logger = structlog.get_logger()

SITE = "ruscorpora.ru"


def _build_query(word: str, corpus_type: str) -> dict[str, Any]:
    return {
        "corpus": {"type": corpus_type},
        "lexGramm": {
            "sectionValues": [
                {
                    "subsectionValues": [
                        {
                            "conditionValues": [
                                {
                                    "fieldName": "lex",
                                    "text": {"v": word},
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    }


def _extract_contexts(payload: dict[str, Any]) -> list[str]:
    contexts: list[str] = []
    for key in ("contexts", "items", "results"):
        block = payload.get(key)
        if isinstance(block, list):
            for item in block:
                if isinstance(item, str):
                    contexts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("context") or item.get("left")
                    if text:
                        contexts.append(str(text))
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                text = item.get("text") or item.get("context")
                if text:
                    contexts.append(str(text))
    return contexts


def run_ruscorpora(
    db: Session,
    *,
    max_items: int = 2000,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest poetic corpus lines from ruscorpora.ru public API."""
    if not source_enabled("ruscorpora"):
        logger.info("ruscorpora.skipped", reason="disabled")
        return {
            "created": 0,
            "merged": 0,
            "skipped": 0,
            "pull_skipped": 0,
            "total_processed": 0,
        }

    token = require_env(
        settings.ruscorpora_api_key,
        name="RUSCORPORA_API_KEY",
        source=SITE,
    )

    config = load_source("ruscorpora")
    api_url = config.get("api_url", "https://ruscorpora.ru")
    queries = config.get("queries") or []
    corpus_type = config.get("corpus_type", "POETIC")
    per_query = int(config.get("max_contexts_per_query", 80))
    language = config.get("language", "ru")
    tier = int(config.get("tier", 1))
    license_hint = config.get("license_hint", "ruscorpora.ru")
    headers = {"Authorization": f"Bearer {token}"}

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info(
        "ruscorpora.ingest_begin",
        max_items=max_items,
        queries=len(queries),
    )

    with ScraperClient() as client:
        for query_cfg in queries:
            if stats["total_processed"] >= max_items:
                break
            word = str(query_cfg.get("word") or query_cfg.get("query") or "")
            if not word:
                continue
            body = _build_query(word, corpus_type)
            url = f"{api_url.rstrip('/')}/api/v1/lex-gramm/concordance"
            work = get_or_create_work(
                db,
                title=f"НКРЯ — {word}",
                kind=WorkKind.poem,
                language=language,
                tier=tier,
                external_slug=f"ruscorpora-{word}"[:120],
            )
            try:
                response = client.fetch_post(
                    url,
                    json=body,
                    pull_log=pull_log,
                    source="ruscorpora",
                    headers=headers,
                )
            except Exception as exc:
                on_error(
                    exc,
                    "ruscorpora.query_failed",
                    word=word,
                    url=url,
                )
                continue
            if response is None:
                stats["pull_skipped"] += 1
                continue

            payload = response.json()
            contexts = _extract_contexts(payload)[:per_query]
            if not contexts:
                stats["skipped"] += 1
                continue

            for index, text in enumerate(contexts):
                if stats["total_processed"] >= max_items:
                    break
                cleaned = " ".join(str(text).split())
                if len(cleaned) < 12:
                    stats["skipped"] += 1
                    continue
                external_id = f"{word}:{index}"
                try:
                    _, created = upsert_fragment(
                        db,
                        text=cleaned,
                        language=language,
                        fragment_type=FragmentType.quote,
                        source_site=SITE,
                        source_url=url,
                        external_id=external_id,
                        license_hint=license_hint,
                        work=work,
                        context=json.dumps(body, ensure_ascii=False)[:200],
                        tags=["ruscorpora"],
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
                    step="ruscorpora",
                )

    db.commit()
    logger.info("ruscorpora.ingest_complete", **stats)
    return stats
