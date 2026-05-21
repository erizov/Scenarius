"""Ingest fragments from Pushdom / configured bulk dataset URLs."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models import FragmentType, WorkKind
from scrapers.errors import IngestConfigError
from scrapers.fail_fast import on_error
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog
from scrapers.sources import load_source, source_enabled

logger = structlog.get_logger()

SITE = "pushdom.ru"


def _rows_from_payload(
    payload: Any,
    *,
    text_field: str,
    title_field: str,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = str(item.get(text_field) or "").strip()
            title = str(item.get(title_field) or "Pushdom dataset")
            if text:
                rows.append((title, text))
    elif isinstance(payload, dict):
        items = payload.get("items") or payload.get("data") or []
        if isinstance(items, list):
            return _rows_from_payload(
                items,
                text_field=text_field,
                title_field=title_field,
            )
    return rows


def _rows_from_csv(text: str, *, text_field: str, title_field: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        text = str(row.get(text_field) or "").strip()
        title = str(row.get(title_field) or "Pushdom dataset")
        if text:
            rows.append((title, text))
    return rows


def run_pushdom(
    db: Session,
    *,
    max_items: int = 1000,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest text rows from configured Pushdom or bulk dataset URLs."""
    if not source_enabled("pushdom"):
        logger.info("pushdom.skipped", reason="disabled")
        return {
            "created": 0,
            "merged": 0,
            "skipped": 0,
            "pull_skipped": 0,
            "total_processed": 0,
        }

    config = load_source("pushdom")
    datasets = config.get("datasets") or []
    if not datasets:
        raise IngestConfigError(
            "pushdom.datasets must list at least one URL "
            "(or disable the source)",
        )

    language = config.get("language", "ru")
    tier = int(config.get("tier", 1))
    license_hint = config.get("license_hint", "pushdom-dataset")

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info(
        "pushdom.ingest_begin",
        max_items=max_items,
        datasets=len(datasets),
    )

    with ScraperClient() as client:
        for dataset in datasets:
            if stats["total_processed"] >= max_items:
                break
            url = str(dataset.get("url") or "")
            if not url:
                continue
            text_field = str(dataset.get("text_field", "text"))
            title_field = str(dataset.get("title_field", "title"))
            fmt = str(dataset.get("format", "json")).lower()
            fragment_type = FragmentType(
                dataset.get("fragment_type", "quote"),
            )
            work_kind = WorkKind(dataset.get("work_kind", "other"))

            try:
                response = client.fetch(
                    url,
                    pull_log=pull_log,
                    source="pushdom",
                )
            except Exception as exc:
                on_error(exc, "pushdom.dataset_failed", url=url)
                continue
            if response is None:
                stats["pull_skipped"] += 1
                continue

            if fmt == "csv":
                rows = _rows_from_csv(
                    response.text,
                    text_field=text_field,
                    title_field=title_field,
                )
            else:
                payload = json.loads(response.text)
                rows = _rows_from_payload(
                    payload,
                    text_field=text_field,
                    title_field=title_field,
                )

            for index, (title, text) in enumerate(rows):
                if stats["total_processed"] >= max_items:
                    break
                work = get_or_create_work(
                    db,
                    title=title,
                    kind=work_kind,
                    language=language,
                    tier=tier,
                    external_slug=f"pushdom-{title}"[:120],
                )
                external_id = f"{url}:{index}"
                try:
                    _, created = upsert_fragment(
                        db,
                        text=text,
                        language=language,
                        fragment_type=fragment_type,
                        source_site=SITE,
                        source_url=url,
                        external_id=external_id,
                        license_hint=license_hint,
                        work=work,
                        tags=["pushdom"],
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
                    step="pushdom",
                )

    db.commit()
    logger.info("pushdom.ingest_complete", **stats)
    return stats
