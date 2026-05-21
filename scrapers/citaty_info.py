"""Parse citaty.info pages."""

import re
from dataclasses import dataclass
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

BASE_URL = "https://citaty.info"
QUOTE_PATH_RE = re.compile(
    r"(?:https?://(?:www\.)?citaty\.info/quote/(\d+)|^/quote/(\d+))",
    re.IGNORECASE,
)
MOVIE_PATH_RE = re.compile(
    r"(?:https?://(?:www\.)?citaty\.info/"
    r"(movie|cartoon|animation|book|series|fairy)/([^/?#]+)|"
    r"^/(movie|cartoon|animation|book|series|fairy)/([^/?#]+))",
    re.IGNORECASE,
)


@dataclass
class ParsedQuote:
    """Quote extracted from citaty.info."""

    text: str
    quote_id: str
    quote_url: str
    work_title: str | None
    work_slug: str | None
    work_kind: WorkKind
    year: int | None
    context: str | None


def _load_citaty_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["citaty_info"]


def _load_sections() -> list[dict[str, Any]]:
    return _load_citaty_config()["sections"]


def _load_list_pages() -> list[dict[str, Any]]:
    return _load_citaty_config().get("list_pages", [])


def _load_priority_paths() -> list[dict[str, Any]]:
    from scrapers.canonical import load_works

    paths: list[dict[str, Any]] = []
    for work in load_works():
        citaty_path = work.get("citaty_path")
        if not citaty_path:
            continue
        paths.append(
            {
                "path": citaty_path,
                "work_kind": work["kind"],
                "tier": work.get("tier", 1),
                "language": work["language"],
            },
        )
    return paths


def _href_path(href: str) -> str:
    """Normalize link to site path (e.g. /movie/slug)."""
    if href.startswith("http"):
        if "citaty.info" not in href.lower():
            return href
        href = href.split("citaty.info", 1)[-1]
    return href.split("?")[0].split("#")[0]


def _kind_from_path(path: str, default: WorkKind) -> WorkKind:
    path = _href_path(path).lower()
    if path.startswith("/cartoon") or path.startswith("/animation"):
        return WorkKind.cartoon
    if path.startswith("/book"):
        return WorkKind.book
    if path.startswith("/fairy"):
        return WorkKind.fairy_tale
    if path.startswith("/movie") or path.startswith("/series"):
        return WorkKind.film
    return default


def _fragment_type_from_section(section: dict[str, Any]) -> FragmentType:
    raw = section.get("fragment_type", "quote")
    return FragmentType(raw)


def _match_group(match: re.Match[str], *groups: int) -> str:
    for idx in groups:
        value = match.group(idx)
        if value:
            return value
    return ""


def extract_quote_links(html: str) -> set[str]:
    """Find unique /quote/ID links in HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = QUOTE_PATH_RE.search(anchor["href"])
        if match:
            links.add(_match_group(match, 1, 2))
    return links


def extract_work_links(html: str) -> set[str]:
    """Find work page paths (/movie/, /cartoon/, etc.)."""
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = MOVIE_PATH_RE.search(anchor["href"])
        if match:
            kind = _match_group(match, 1, 3)
            slug = _match_group(match, 2, 4)
            links.add(f"/{kind}/{slug}")
    return links


def parse_quote_page(
    html: str,
    quote_id: str,
    quote_url: str,
    default_kind: WorkKind,
) -> ParsedQuote | None:
    """Parse a single quote page."""
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.find("h1")
    if heading:
        text = heading.get_text(" ", strip=True)
    else:
        title_tag = soup.find("title")
        text = title_tag.get_text(" ", strip=True) if title_tag else ""
        text = re.sub(r"\s*©.*$", "", text).strip()

    if not text or len(text) < 3:
        return None

    work_title = None
    work_slug = None
    year = None
    for anchor in soup.find_all("a", href=True):
        match = MOVIE_PATH_RE.search(anchor["href"])
        if match:
            work_title = anchor.get_text(" ", strip=True)
            work_slug = _match_group(match, 2, 4)
            break

    context = None
    for paragraph in soup.find_all("p"):
        raw = paragraph.get_text(" ", strip=True)
        if raw and raw != text and len(raw) < 300:
            context = raw
            break

    year_match = re.search(r"\b(18|19|20)\d{2}\b", soup.get_text(" ", strip=True))
    if year_match:
        year = int(year_match.group(0))

    return ParsedQuote(
        text=text,
        quote_id=quote_id,
        quote_url=quote_url,
        work_title=work_title,
        work_slug=work_slug,
        work_kind=default_kind,
        year=year,
        context=context,
    )


def _ingest_quote(
    db: Session,
    client: ScraperClient,
    quote_id: str,
    section: dict[str, Any],
    stats: dict[str, int],
    *,
    pull_log: PullLog | None = None,
) -> bool:
    """Ingest one quote. Returns False when the URL was skipped via pull log."""
    quote_url = f"{BASE_URL}/quote/{quote_id}"
    try:
        response = client.fetch(
            quote_url,
            pull_log=pull_log,
            source="citaty_info",
        )
        if response is None:
            stats["pull_skipped"] += 1
            return False
        html = response.text
    except Exception as exc:
        on_error(
            exc,
            "citaty.quote_fetch_failed",
            quote_id=quote_id,
        )
        stats["skipped"] += 1
        return True

    default_kind = WorkKind(section.get("work_kind", "film"))
    parsed = parse_quote_page(html, quote_id, quote_url, default_kind)
    if parsed is None:
        stats["skipped"] += 1
        return True

    work = None
    if parsed.work_title:
        work = get_or_create_work(
            db,
            title=parsed.work_title,
            kind=parsed.work_kind,
            language=section.get("language", "ru"),
            tier=section.get("tier", 1),
            year=parsed.year,
            external_slug=f"citaty-{parsed.work_slug}" if parsed.work_slug else None,
        )

    fragment_type = _fragment_type_from_section(section)
    if "—" in parsed.text and len(parsed.text) > 80:
        fragment_type = FragmentType.dialogue

    _, created = upsert_fragment(
        db,
        text=parsed.text,
        language=section.get("language", "ru"),
        fragment_type=fragment_type,
        source_site="citaty.info",
        source_url=quote_url,
        external_id=quote_id,
        license_hint="scrape-with-attribution",
        work=work,
        context=parsed.context,
        tags=["citaty_info"],
    )
    if created:
        stats["created"] += 1
    else:
        stats["merged"] += 1

    processed = stats["created"] + stats["merged"] + stats["skipped"]
    if processed % 10 == 0:
        logger.info("citaty.progress", **stats)
    maybe_commit_batch(db, processed, step="citaty")
    return True


def _ingest_work_page(
    db: Session,
    client: ScraperClient,
    work_path: str,
    section: dict[str, Any],
    stats: dict[str, int],
    max_quotes: int,
    *,
    pull_log: PullLog | None = None,
) -> None:
    url = urljoin(BASE_URL, work_path)
    try:
        response = client.fetch(url, pull_log=pull_log, source="citaty_info")
        if response is None:
            stats["pull_skipped"] += 1
            return
        html = response.text
    except Exception as exc:
        on_error(exc, "citaty.work_fetch_failed", url=url)
        return

    quote_ids = list(extract_quote_links(html))[:max_quotes]
    for quote_id in quote_ids:
        if stats["total_processed"] >= max_quotes:
            return
        if _ingest_quote(
            db,
            client,
            quote_id,
            section,
            stats,
            pull_log=pull_log,
        ):
            stats["total_processed"] += 1


def _ingest_section_page(
    db: Session,
    client: ScraperClient,
    section: dict[str, Any],
    stats: dict[str, int],
    max_quotes: int,
    *,
    max_works: int,
    pull_log: PullLog | None = None,
) -> None:
    """Ingest quotes from a section, list, or priority work path."""
    section_url = urljoin(BASE_URL, section["path"])
    try:
        response = client.fetch(
            section_url,
            pull_log=pull_log,
            source="citaty_info",
        )
        if response is None:
            stats["pull_skipped"] += 1
            return
        html = response.text
    except Exception as exc:
        on_error(
            exc,
            "citaty.section_failed",
            path=section["path"],
        )
        return

    work_paths = list(extract_work_links(html))[:max_works]
    quote_ids = list(extract_quote_links(html))

    for quote_id in quote_ids:
        if stats["total_processed"] >= max_quotes:
            return
        if _ingest_quote(
            db,
            client,
            quote_id,
            section,
            stats,
            pull_log=pull_log,
        ):
            stats["total_processed"] += 1

    for work_path in work_paths:
        if stats["total_processed"] >= max_quotes:
            return
        _ingest_work_page(
            db,
            client,
            work_path,
            section,
            stats,
            max_quotes - stats["total_processed"],
            pull_log=pull_log,
        )


def run_citaty_info(
    db: Session,
    *,
    max_quotes: int = 1000,
    max_works_per_section: int = 50,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest quotes from citaty.info section and work pages."""
    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    sections = _load_sections()
    list_pages = _load_list_pages()
    priority_paths = _load_priority_paths()
    logger.info(
        "citaty.ingest_begin",
        max_quotes=max_quotes,
        sections=len(sections),
        list_pages=len(list_pages),
        priority_paths=len(priority_paths),
    )

    ingest_order: list[tuple[str, list[dict[str, Any]]]] = [
        ("priority", priority_paths),
        ("list", list_pages),
        ("section", sections),
    ]

    with ScraperClient() as client:
        for phase, items in ingest_order:
            for section in items:
                if stats["total_processed"] >= max_quotes:
                    break
                logger.info(
                    "citaty.section_start",
                    phase=phase,
                    path=section["path"],
                )
                _ingest_section_page(
                    db,
                    client,
                    section,
                    stats,
                    max_quotes,
                    max_works=max_works_per_section,
                    pull_log=pull_log,
                )

    db.commit()
    logger.info("citaty.ingest_complete", **stats)
    return stats
