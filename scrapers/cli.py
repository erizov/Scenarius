"""CLI for scrapers and seed tasks."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import structlog

from app.db import SessionLocal
from scrapers import (
    anekdot_ru,
    citaty_info,
    culture_ru,
    gutenberg,
    ingest_stats,
    opensubtitles,
    pipeline,
    poetrydb,
    pushdom,
    quotable,
    ruscorpora,
    seed,
    wikiquote,
    wikisource,
    wiktionary,
)
from scrapers.corpus import ingest_defaults
from scrapers.fail_fast import fail_fast_context
from scrapers.pull_log import PullLog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

_DEFAULTS = ingest_defaults()


def _add_pull_log_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-pull-log",
        action="store_true",
        help="Refetch all URLs; do not skip prior successful pulls",
    )
    parser.add_argument(
        "--pull-log-path",
        type=str,
        default=None,
        help="Pull log JSON path (default: data/ingest_pull_log.json)",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue after HTTP/ingest errors (default: stop on first error)",
    )


def _make_pull_log(args: argparse.Namespace) -> PullLog:
    log_path = Path(args.pull_log_path) if args.pull_log_path else None
    return PullLog(log_path, enabled=not args.no_pull_log)


def _run_pull_ingest(
    args: argparse.Namespace,
    runner: Callable[..., dict],
) -> int:
    """Run a single-source ingest with pull log and fail-fast context."""
    pull_log = _make_pull_log(args)
    fail_fast = not args.no_fail_fast
    with fail_fast_context(fail_fast):
        with SessionLocal() as db:
            result = runner(db, pull_log)
    pull_log.save()
    print(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for python -m scrapers.cli."""
    parser = argparse.ArgumentParser(description="Scenarius ingest tools")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Sync canonical works and verified must-haves")

    pull_parent = argparse.ArgumentParser(add_help=False)
    _add_pull_log_args(pull_parent)

    citaty = sub.add_parser(
        "citaty",
        help="Ingest citaty.info",
        parents=[pull_parent],
    )
    citaty.add_argument("--max", type=int, default=_DEFAULTS["citaty_max"])

    wq_ru = sub.add_parser(
        "wikiquote-ru",
        help="Ingest ru.wikiquote.org",
        parents=[pull_parent],
    )
    wq_ru.add_argument(
        "--max-pages",
        type=int,
        default=_DEFAULTS["wikiquote_ru_max_pages"],
    )

    wq_en = sub.add_parser(
        "wikiquote-en",
        help="Ingest en.wikiquote.org",
        parents=[pull_parent],
    )
    wq_en.add_argument(
        "--max-pages",
        type=int,
        default=_DEFAULTS["wikiquote_en_max_pages"],
    )

    ws_ru = sub.add_parser(
        "wikisource-ru",
        help="Ingest ru.wikisource.org (fairy tales)",
        parents=[pull_parent],
    )
    ws_ru.add_argument(
        "--max-pages",
        type=int,
        default=_DEFAULTS["wikisource_ru_max_pages"],
    )

    ws_en = sub.add_parser(
        "wikisource-en",
        help="Ingest en.wikisource.org",
        parents=[pull_parent],
    )
    ws_en.add_argument(
        "--max-pages",
        type=int,
        default=_DEFAULTS["wikisource_en_max_pages"],
    )

    wt_ru = sub.add_parser(
        "wiktionary-ru",
        help="Ingest ru.wiktionary.org (proverbs)",
        parents=[pull_parent],
    )
    wt_ru.add_argument(
        "--max-pages",
        type=int,
        default=_DEFAULTS["wiktionary_ru_max_pages"],
    )

    culture = sub.add_parser(
        "culture",
        help="Ingest culture.ru (API)",
        parents=[pull_parent],
    )
    culture.add_argument("--max", type=int, default=_DEFAULTS["culture_max"])
    culture.add_argument("--max-pages", type=int, default=_DEFAULTS["culture_pages"])

    anekdot = sub.add_parser(
        "anekdot",
        help="Ingest anekdot.ru feeds",
        parents=[pull_parent],
    )
    anekdot.add_argument("--max", type=int, default=_DEFAULTS["anekdot_max"])
    anekdot.add_argument("--max-pages", type=int, default=_DEFAULTS["anekdot_pages"])

    ingest_all = sub.add_parser(
        "ingest-all",
        help="All sources toward 50k corpus target",
        parents=[pull_parent],
    )
    ingest_all.add_argument("--citaty-max", type=int, default=_DEFAULTS["citaty_max"])
    ingest_all.add_argument("--culture-max", type=int, default=_DEFAULTS["culture_max"])
    ingest_all.add_argument("--anekdot-max", type=int, default=_DEFAULTS["anekdot_max"])
    ingest_all.add_argument(
        "--wikisource-ru-max-pages",
        type=int,
        default=_DEFAULTS["wikisource_ru_max_pages"],
    )
    ingest_all.add_argument(
        "--wiktionary-ru-max-pages",
        type=int,
        default=_DEFAULTS["wiktionary_ru_max_pages"],
    )
    ingest_all.add_argument(
        "--ru-max-pages",
        type=int,
        default=_DEFAULTS["wikiquote_ru_max_pages"],
    )
    ingest_all.add_argument(
        "--en-max-pages",
        type=int,
        default=_DEFAULTS["wikiquote_en_max_pages"],
    )
    ingest_all.add_argument(
        "--wikisource-en-max-pages",
        type=int,
        default=_DEFAULTS["wikisource_en_max_pages"],
    )
    ingest_all.add_argument(
        "--poetrydb-max",
        type=int,
        default=_DEFAULTS["poetrydb_max"],
    )
    ingest_all.add_argument(
        "--gutenberg-max",
        type=int,
        default=_DEFAULTS["gutenberg_max"],
    )
    ingest_all.add_argument(
        "--quotable-max",
        type=int,
        default=_DEFAULTS["quotable_max"],
    )
    ingest_all.add_argument(
        "--opensubtitles-max",
        type=int,
        default=_DEFAULTS["opensubtitles_max"],
    )
    ingest_all.add_argument(
        "--ruscorpora-max",
        type=int,
        default=_DEFAULTS["ruscorpora_max"],
    )
    ingest_all.add_argument(
        "--pushdom-max",
        type=int,
        default=_DEFAULTS["pushdom_max"],
    )

    poetry = sub.add_parser(
        "poetrydb",
        help="Ingest poetrydb.org",
        parents=[pull_parent],
    )
    poetry.add_argument("--max", type=int, default=_DEFAULTS["poetrydb_max"])

    gutenberg_cmd = sub.add_parser(
        "gutenberg",
        help="Ingest Project Gutenberg books",
        parents=[pull_parent],
    )
    gutenberg_cmd.add_argument("--max", type=int, default=_DEFAULTS["gutenberg_max"])

    quotable_cmd = sub.add_parser(
        "quotable",
        help="Ingest quotable.io",
        parents=[pull_parent],
    )
    quotable_cmd.add_argument("--max", type=int, default=_DEFAULTS["quotable_max"])

    opensub = sub.add_parser(
        "opensubtitles",
        help="Ingest OpenSubtitles dialogue lines",
        parents=[pull_parent],
    )
    opensub.add_argument(
        "--max",
        type=int,
        default=_DEFAULTS["opensubtitles_max"],
    )

    ruscorp = sub.add_parser(
        "ruscorpora",
        help="Ingest НКРЯ poetic corpus",
        parents=[pull_parent],
    )
    ruscorp.add_argument("--max", type=int, default=_DEFAULTS["ruscorpora_max"])

    pushdom_cmd = sub.add_parser(
        "pushdom",
        help="Ingest Pushdom bulk datasets",
        parents=[pull_parent],
    )
    pushdom_cmd.add_argument("--max", type=int, default=_DEFAULTS["pushdom_max"])

    stats_parser = sub.add_parser(
        "stats",
        help="Show ingestion totals (ru/en, authors, sources, review)",
    )
    stats_parser.add_argument(
        "--watch",
        action="store_true",
        help="Refresh while ingest runs in another terminal",
    )
    stats_parser.add_argument("--interval", type=float, default=5.0)
    stats_parser.add_argument("--recent-minutes", type=int, default=5)

    args = parser.parse_args(argv)

    if args.command == "seed":
        with SessionLocal() as db:
            seed.run_seed(db)
        return 0

    if args.command == "citaty":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: citaty_info.run_citaty_info(
                db,
                max_quotes=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "wikiquote-ru":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: wikiquote.run_wikiquote_ru(
                db,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "wikiquote-en":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: wikiquote.run_wikiquote_en(
                db,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "wikisource-ru":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: wikisource.run_wikisource_ru(
                db,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "wikisource-en":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: wikisource.run_wikisource_en(
                db,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "wiktionary-ru":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: wiktionary.run_wiktionary_ru(
                db,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "culture":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: culture_ru.run_culture_ru(
                db,
                max_items=args.max,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "anekdot":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: anekdot_ru.run_anekdot_ru(
                db,
                max_items=args.max,
                max_pages=args.max_pages,
                pull_log=pull_log,
            ),
        )

    if args.command == "poetrydb":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: poetrydb.run_poetrydb(
                db,
                max_items=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "gutenberg":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: gutenberg.run_gutenberg(
                db,
                max_items=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "quotable":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: quotable.run_quotable(
                db,
                max_items=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "opensubtitles":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: opensubtitles.run_opensubtitles(
                db,
                max_items=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "ruscorpora":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: ruscorpora.run_ruscorpora(
                db,
                max_items=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "pushdom":
        return _run_pull_ingest(
            args,
            lambda db, pull_log: pushdom.run_pushdom(
                db,
                max_items=args.max,
                pull_log=pull_log,
            ),
        )

    if args.command == "ingest-all":
        pull_log = _make_pull_log(args)
        fail_fast = not args.no_fail_fast
        with fail_fast_context(fail_fast):
            with SessionLocal() as db:
                results = pipeline.run_all(
                    db,
                    citaty_max=args.citaty_max,
                    culture_max=args.culture_max,
                    anekdot_max=args.anekdot_max,
                    wikisource_ru_max_pages=args.wikisource_ru_max_pages,
                    wiktionary_ru_max_pages=args.wiktionary_ru_max_pages,
                    wikiquote_ru_max_pages=args.ru_max_pages,
                    wikiquote_en_max_pages=args.en_max_pages,
                    wikisource_en_max_pages=args.wikisource_en_max_pages,
                    poetrydb_max=args.poetrydb_max,
                    gutenberg_max=args.gutenberg_max,
                    quotable_max=args.quotable_max,
                    opensubtitles_max=args.opensubtitles_max,
                    ruscorpora_max=args.ruscorpora_max,
                    pushdom_max=args.pushdom_max,
                    pull_log=pull_log,
                    fail_fast=fail_fast,
                )
        print(results)
        return 0

    if args.command == "stats":
        return ingest_stats.main(
            [
                *(["--watch"] if args.watch else []),
                "--interval",
                str(args.interval),
                "--recent-minutes",
                str(args.recent_minutes),
            ],
        )

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
