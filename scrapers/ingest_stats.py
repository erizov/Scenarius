"""Ingestion progress statistics."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Fragment, Person, PersonRole, SourceRef, Work, WorkPerson
from scrapers.corpus import ingest_defaults


@dataclass
class IngestTotals:
    """Aggregated corpus counters."""

    fragments: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    people: int = 0
    authors: int = 0
    works: int = 0
    sources: dict[str, int] = field(default_factory=dict)
    embeddings: int | None = None
    recent_fragments: int = 0
    scraped_at: datetime | None = None
    verified: int = 0
    review_pending: int = 0
    corpus_target: int = 50000


def _embeddings_table_exists(db: Session) -> bool:
    return bool(
        db.execute(
            text("SELECT to_regclass('public.fragment_embeddings') IS NOT NULL"),
        ).scalar(),
    )


def collect_totals(
    db: Session,
    *,
    recent_minutes: int = 5,
) -> IngestTotals:
    """Query current ingestion totals from the database."""
    totals = IngestTotals()

    totals.fragments = db.scalar(select(func.count()).select_from(Fragment)) or 0

    lang_rows = db.execute(
        select(Fragment.language, func.count())
        .group_by(Fragment.language)
        .order_by(Fragment.language),
    ).all()
    totals.languages = {lang: count for lang, count in lang_rows}

    totals.people = db.scalar(select(func.count()).select_from(Person)) or 0
    totals.authors = db.scalar(
        select(func.count(func.distinct(WorkPerson.person_id)))
        .where(WorkPerson.role == PersonRole.author),
    ) or 0
    totals.works = db.scalar(select(func.count()).select_from(Work)) or 0

    source_rows = db.execute(
        select(SourceRef.source_site, func.count(func.distinct(SourceRef.fragment_id)))
        .group_by(SourceRef.source_site)
        .order_by(SourceRef.source_site),
    ).all()
    totals.sources = {site: count for site, count in source_rows}

    if _embeddings_table_exists(db):
        totals.embeddings = db.scalar(
            text("SELECT COUNT(*) FROM fragment_embeddings"),
        ) or 0

    if recent_minutes > 0:
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=recent_minutes)
        totals.recent_fragments = db.scalar(
            select(func.count())
            .select_from(Fragment)
            .where(Fragment.created_at >= cutoff),
        ) or 0

    totals.scraped_at = db.scalar(
        select(func.max(SourceRef.scraped_at)),
    )
    totals.verified = db.scalar(
        select(func.count()).select_from(Fragment).where(Fragment.verified.is_(True)),
    ) or 0
    totals.review_pending = db.scalar(
        select(func.count())
        .select_from(Fragment)
        .where(
            Fragment.verified.is_(False),
            Fragment.meta["review_status"].as_string() == "pending",
        ),
    ) or 0
    cfg = ingest_defaults()
    totals.corpus_target = cfg["target_total"]
    return totals


def _lang_count(totals: IngestTotals, code: str) -> int:
    return totals.languages.get(code, 0)


def format_totals(
    totals: IngestTotals,
    *,
    recent_minutes: int = 5,
) -> str:
    """Render totals as a human-readable report."""
    lines = [
        "Scenarius ingest totals",
        "=======================",
        f"Fragments : {totals.fragments}",
        f"  ru      : {_lang_count(totals, 'ru')}",
        f"  en      : {_lang_count(totals, 'en')}",
    ]

    other_langs = {
        lang: count
        for lang, count in totals.languages.items()
        if lang not in {"ru", "en"}
    }
    for lang, count in sorted(other_langs.items()):
        lines.append(f"  {lang:<7}: {count}")

    lines.extend(
        [
            f"People    : {totals.people}",
            f"Authors   : {totals.authors} (linked to works)",
            f"Works     : {totals.works}",
            f"Verified  : {totals.verified}",
            f"Review Q  : {totals.review_pending} pending",
            f"Target    : {totals.fragments} / {totals.corpus_target} fragments",
            "Sources   :",
        ],
    )

    if totals.sources:
        for site, count in sorted(
            totals.sources.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            lines.append(f"  {site:<20}: {count}")
    else:
        lines.append("  (none)")

    if totals.embeddings is not None:
        lines.append(f"Embeddings: {totals.embeddings}")

    if recent_minutes > 0:
        lines.append(
            f"Recent    : +{totals.recent_fragments} fragments "
            f"(last {recent_minutes} min)",
        )

    if totals.scraped_at is not None:
        lines.append(f"Last scrape: {totals.scraped_at.isoformat()}")

    return "\n".join(lines)


def print_totals(
    db: Session,
    *,
    recent_minutes: int = 5,
) -> IngestTotals:
    """Print totals and return the collected snapshot."""
    totals = collect_totals(db, recent_minutes=recent_minutes)
    print(format_totals(totals, recent_minutes=recent_minutes))
    return totals


def watch_totals(
    *,
    interval: float = 5.0,
    recent_minutes: int = 5,
) -> None:
    """Poll and print totals until interrupted."""
    previous: IngestTotals | None = None
    while True:
        if sys.platform == "win32":
            import os

            os.system("cls")
        else:
            print("\033[2J\033[H", end="")

        with SessionLocal() as db:
            totals = print_totals(db, recent_minutes=recent_minutes)

        if previous is not None:
            delta = totals.fragments - previous.fragments
            if delta:
                print(f"\nDelta since last refresh: +{delta} fragments")

        previous = totals
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ingestion stats."""
    parser = argparse.ArgumentParser(
        description="Show Scenarius ingestion running totals",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Refresh totals periodically while ingest runs",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Refresh interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--recent-minutes",
        type=int,
        default=5,
        help="Window for recent fragment count (default: 5, 0=disable)",
    )
    args = parser.parse_args(argv)

    if args.watch:
        try:
            watch_totals(
                interval=args.interval,
                recent_minutes=args.recent_minutes,
            )
        except KeyboardInterrupt:
            print("\nStopped.")
        return 0

    with SessionLocal() as db:
        print_totals(db, recent_minutes=args.recent_minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
