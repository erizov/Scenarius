"""Run full ingest pipeline in priority order."""

from __future__ import annotations

from typing import Any, Callable

import structlog
from sqlalchemy.orm import Session

from scrapers import (
    anekdot_ru,
    citaty_info,
    culture_ru,
    gutenberg,
    opensubtitles,
    poetrydb,
    pushdom,
    quotable,
    ruscorpora,
    wikiquote,
    wikisource,
    wiktionary,
)
from scrapers.corpus import ingest_defaults
from scrapers.errors import IngestConfigError
from scrapers.fail_fast import fail_fast_context
from scrapers.pull_log import PullLog
from scrapers.sources import source_enabled

logger = structlog.get_logger()
_DEFAULTS = ingest_defaults()


def run_all(
    db: Session,
    *,
    citaty_max: int | None = None,
    culture_max: int | None = None,
    anekdot_max: int | None = None,
    wikisource_ru_max_pages: int | None = None,
    wiktionary_ru_max_pages: int | None = None,
    wikiquote_ru_max_pages: int | None = None,
    wikiquote_en_max_pages: int | None = None,
    wikisource_en_max_pages: int | None = None,
    poetrydb_max: int | None = None,
    gutenberg_max: int | None = None,
    quotable_max: int | None = None,
    opensubtitles_max: int | None = None,
    ruscorpora_max: int | None = None,
    pushdom_max: int | None = None,
    culture_pages: int | None = None,
    anekdot_pages: int | None = None,
    pull_log: PullLog | None = None,
    fail_fast: bool = True,
) -> dict[str, Any]:
    """Ingest all configured sources in priority order."""
    citaty_max = citaty_max if citaty_max is not None else _DEFAULTS["citaty_max"]
    culture_max = culture_max if culture_max is not None else _DEFAULTS["culture_max"]
    anekdot_max = anekdot_max if anekdot_max is not None else _DEFAULTS["anekdot_max"]
    wikisource_ru_max_pages = (
        wikisource_ru_max_pages
        if wikisource_ru_max_pages is not None
        else _DEFAULTS["wikisource_ru_max_pages"]
    )
    wiktionary_ru_max_pages = (
        wiktionary_ru_max_pages
        if wiktionary_ru_max_pages is not None
        else _DEFAULTS["wiktionary_ru_max_pages"]
    )
    wikiquote_ru_max_pages = (
        wikiquote_ru_max_pages
        if wikiquote_ru_max_pages is not None
        else _DEFAULTS["wikiquote_ru_max_pages"]
    )
    wikiquote_en_max_pages = (
        wikiquote_en_max_pages
        if wikiquote_en_max_pages is not None
        else _DEFAULTS["wikiquote_en_max_pages"]
    )
    wikisource_en_max_pages = (
        wikisource_en_max_pages
        if wikisource_en_max_pages is not None
        else _DEFAULTS["wikisource_en_max_pages"]
    )
    poetrydb_max = (
        poetrydb_max if poetrydb_max is not None else _DEFAULTS["poetrydb_max"]
    )
    gutenberg_max = (
        gutenberg_max if gutenberg_max is not None else _DEFAULTS["gutenberg_max"]
    )
    quotable_max = (
        quotable_max if quotable_max is not None else _DEFAULTS["quotable_max"]
    )
    opensubtitles_max = (
        opensubtitles_max
        if opensubtitles_max is not None
        else _DEFAULTS["opensubtitles_max"]
    )
    ruscorpora_max = (
        ruscorpora_max if ruscorpora_max is not None else _DEFAULTS["ruscorpora_max"]
    )
    pushdom_max = (
        pushdom_max if pushdom_max is not None else _DEFAULTS["pushdom_max"]
    )
    culture_pages = (
        culture_pages if culture_pages is not None else _DEFAULTS["culture_pages"]
    )
    anekdot_pages = (
        anekdot_pages if anekdot_pages is not None else _DEFAULTS["anekdot_pages"]
    )

    results: dict[str, Any] = {}
    target = _DEFAULTS["target_total"]

    steps: list[tuple[str, Callable[[], dict[str, Any]], dict[str, Any]]] = [
        (
            "citaty_info",
            lambda: citaty_info.run_citaty_info(
                db,
                max_quotes=citaty_max,
                pull_log=pull_log,
            ),
            {"max_quotes": citaty_max},
        ),
        (
            "culture_ru",
            lambda: culture_ru.run_culture_ru(
                db,
                max_items=culture_max,
                max_pages=culture_pages,
                pull_log=pull_log,
            ),
            {"max_items": culture_max},
        ),
        (
            "anekdot_ru",
            lambda: anekdot_ru.run_anekdot_ru(
                db,
                max_items=anekdot_max,
                max_pages=anekdot_pages,
                pull_log=pull_log,
            ),
            {"max_items": anekdot_max},
        ),
        (
            "wikisource_ru",
            lambda: wikisource.run_wikisource_ru(
                db,
                max_pages=wikisource_ru_max_pages,
                pull_log=pull_log,
            ),
            {"max_pages": wikisource_ru_max_pages},
        ),
        (
            "wiktionary_ru",
            lambda: wiktionary.run_wiktionary_ru(
                db,
                max_pages=wiktionary_ru_max_pages,
                pull_log=pull_log,
            ),
            {"max_pages": wiktionary_ru_max_pages},
        ),
        (
            "wikiquote_ru",
            lambda: wikiquote.run_wikiquote_ru(
                db,
                max_pages=wikiquote_ru_max_pages,
                pull_log=pull_log,
            ),
            {"max_pages": wikiquote_ru_max_pages},
        ),
        (
            "wikiquote_en",
            lambda: wikiquote.run_wikiquote_en(
                db,
                max_pages=wikiquote_en_max_pages,
                pull_log=pull_log,
            ),
            {"max_pages": wikiquote_en_max_pages},
        ),
        (
            "wikisource_en",
            lambda: wikisource.run_wikisource_en(
                db,
                max_pages=wikisource_en_max_pages,
                pull_log=pull_log,
            ),
            {"max_pages": wikisource_en_max_pages},
        ),
        (
            "poetrydb",
            lambda: poetrydb.run_poetrydb(
                db,
                max_items=poetrydb_max,
                pull_log=pull_log,
            ),
            {"max_items": poetrydb_max},
        ),
        (
            "gutenberg",
            lambda: gutenberg.run_gutenberg(
                db,
                max_items=gutenberg_max,
                pull_log=pull_log,
            ),
            {"max_items": gutenberg_max},
        ),
        (
            "quotable",
            lambda: quotable.run_quotable(
                db,
                max_items=quotable_max,
                pull_log=pull_log,
            ),
            {"max_items": quotable_max},
        ),
        (
            "opensubtitles",
            lambda: opensubtitles.run_opensubtitles(
                db,
                max_items=opensubtitles_max,
                pull_log=pull_log,
            ),
            {"max_items": opensubtitles_max},
        ),
        (
            "ruscorpora",
            lambda: ruscorpora.run_ruscorpora(
                db,
                max_items=ruscorpora_max,
                pull_log=pull_log,
            ),
            {"max_items": ruscorpora_max},
        ),
        (
            "pushdom",
            lambda: pushdom.run_pushdom(
                db,
                max_items=pushdom_max,
                pull_log=pull_log,
            ),
            {"max_items": pushdom_max},
        ),
    ]

    with fail_fast_context(fail_fast):
        for step_name, runner, meta in steps:
            if not source_enabled(step_name):
                logger.info("ingest.skipped", step=step_name, reason="disabled")
                results[step_name] = {"skipped": True, "reason": "disabled"}
                continue
            logger.info(
                "ingest.start",
                step=step_name,
                corpus_target=target,
                fail_fast=fail_fast,
                **meta,
            )
            try:
                results[step_name] = runner()
            except IngestConfigError:
                if pull_log is not None:
                    pull_log.save()
                raise
            except Exception as exc:
                if pull_log is not None:
                    pull_log.save()
                logger.error(
                    "ingest.step_failed",
                    step=step_name,
                    error=str(exc),
                    fail_fast=fail_fast,
                )
                if fail_fast:
                    raise
                results[step_name] = {"error": str(exc)}
                continue
            logger.info(
                "ingest.step_complete",
                step=step_name,
                **results[step_name],
            )
            if pull_log is not None:
                pull_log.save()

    totals = {"created": 0, "merged": 0, "skipped": 0, "pull_skipped": 0}
    for step_name, step_stats in results.items():
        if step_name in {"totals", "corpus_target", "pull_log"}:
            continue
        if not isinstance(step_stats, dict):
            continue
        for key in totals:
            totals[key] += step_stats.get(key, 0)

    results["totals"] = totals
    results["corpus_target"] = target
    if pull_log is not None:
        pull_log.save()
        results["pull_log"] = pull_log.summary()
    logger.info("ingest.complete", corpus_target=target, **totals)
    return results
