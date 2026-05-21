"""Shared MediaWiki API ingest (Wikiquote, Wikisource, Wiktionary)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import structlog
import yaml
from sqlalchemy.orm import Session

from app.models import FragmentType, WorkKind
from scrapers.fail_fast import on_error
from scrapers.http_client import ScraperClient
from scrapers.ingest import get_or_create_work, maybe_commit_batch, upsert_fragment
from scrapers.pull_log import PullLog

logger = structlog.get_logger()

TAG_RE = re.compile(r"<[^>]+>")
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
WIKI_LINK_RE = re.compile(r"\[\[([^|\]#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")


def _load_sources() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "sources.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_mediawiki_config(source_key: str) -> dict[str, Any]:
    """Load a MediaWiki source block from sources.yaml."""
    data = _load_sources()
    if source_key not in data:
        raise KeyError(f"Unknown mediawiki source: {source_key}")
    return data[source_key]


def _api_get(
    client: ScraperClient,
    api_url: str,
    *,
    pull_log: PullLog | None = None,
    source: str,
    **params: Any,
) -> dict | None:
    params["format"] = "json"
    return client.get_json(
        api_url,
        params=params,
        pull_log=pull_log,
        source=source,
    )


def _category_members(
    client: ScraperClient,
    api_url: str,
    category: str,
    limit: int,
    *,
    depth: int = 0,
    max_depth: int = 2,
    pull_log: PullLog | None = None,
    source: str,
    stats: dict[str, int],
) -> list[str]:
    """List page titles in a MediaWiki category (recurse subcats)."""
    titles: list[str] = []
    continue_token: str | None = None
    while len(titles) < limit:
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": min(50, limit - len(titles)),
        }
        if continue_token:
            params["cmcontinue"] = continue_token
        payload = _api_get(
            client,
            api_url,
            pull_log=pull_log,
            source=source,
            **params,
        )
        if payload is None:
            stats["pull_skipped"] += 1
            break
        members = payload.get("query", {}).get("categorymembers", [])
        for item in members:
            if len(titles) >= limit:
                break
            title = item.get("title", "")
            ns = item.get("ns", 0)
            if not title:
                continue
            if ns == 14 or title.startswith(("Category:", "Категория:")):
                if depth < max_depth:
                    sub = _category_members(
                        client,
                        api_url,
                        title,
                        limit - len(titles),
                        depth=depth + 1,
                        max_depth=max_depth,
                        pull_log=pull_log,
                        source=source,
                        stats=stats,
                    )
                    titles.extend(sub)
                continue
            titles.append(title)
        cont = payload.get("continue", {})
        continue_token = cont.get("cmcontinue")
        if not continue_token or not members:
            break
    return titles[:limit]


def _page_wikitext(
    client: ScraperClient,
    api_url: str,
    title: str,
    *,
    pull_log: PullLog | None = None,
    source: str,
) -> str | None:
    payload = _api_get(
        client,
        api_url,
        pull_log=pull_log,
        source=source,
        action="parse",
        page=title,
        prop="wikitext",
        formatversion=2,
    )
    if payload is None:
        return None
    return payload.get("parse", {}).get("wikitext", "")


def _clean_wiki_line(line: str) -> str:
    cleaned = TAG_RE.sub("", line)
    cleaned = TEMPLATE_RE.sub("", cleaned)
    cleaned = WIKI_LINK_RE.sub(
        lambda match: match.group(2) or match.group(1),
        cleaned,
    )
    cleaned = re.sub(r"'''|''", "", cleaned)
    return cleaned.strip(" \"'*#:")


def extract_wikiquote_lines(wikitext: str) -> list[str]:
    """Extract bullet quote lines from Wikiquote wikitext."""
    quotes: list[str] = []
    for line in wikitext.splitlines():
        line = line.strip()
        if not line.startswith("*") or line.startswith("**"):
            continue
        cleaned = _clean_wiki_line(line.lstrip("* ").strip())
        if len(cleaned) >= 10 and not cleaned.startswith("{{"):
            quotes.append(cleaned)
    return quotes


def extract_wikisource_passages(wikitext: str, *, limit: int = 12) -> list[str]:
    """Extract prose/poem passages from Wikisource pages."""
    passages: list[str] = []
    seen: set[str] = set()

    def add_text(raw: str) -> None:
        if len(passages) >= limit:
            return
        cleaned = _clean_wiki_line(raw)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) < 25 or cleaned.startswith("{{"):
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        passages.append(cleaned)

    in_poem = False
    for line in wikitext.splitlines():
        stripped = line.strip()
        if stripped.startswith("<poem"):
            in_poem = True
            continue
        if stripped.startswith("</poem"):
            in_poem = False
            continue
        if in_poem:
            if stripped.startswith("|"):
                add_text(stripped.lstrip("| "))
            continue
        if stripped.startswith(("=", "{", "[[Категория", "[[Category:")):
            continue
        if stripped.startswith(("*", "#", ";", "|")):
            add_text(stripped.lstrip("*#;| "))
            continue
        if stripped:
            add_text(stripped)

    if not passages:
        blob = _clean_wiki_line(wikitext)
        blob = re.sub(r"\s+", " ", blob)
        for chunk in re.split(r"(?<=[.!?…])\s+", blob):
            add_text(chunk)

    return passages[:limit]


def extract_wiktionary_entries(title: str, wikitext: str) -> list[str]:
    """Extract proverb/phrase text from Wiktionary pages."""
    entries: list[str] = []
    seen: set[str] = set()

    def add_text(raw: str) -> None:
        cleaned = _clean_wiki_line(raw)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) < 8:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        entries.append(cleaned)

    title_clean = _clean_wiki_line(title)
    if len(title_clean) >= 8 and not title_clean.startswith("Категория"):
        add_text(title_clean)

    for line in wikitext.splitlines():
        stripped = line.strip()
        if stripped.startswith(("=", "{", "[[Категория", "[[Category:")):
            continue
        if re.match(r"^#+\s*", stripped):
            add_text(re.sub(r"^#+\s*", "", stripped))
            continue
        if stripped.startswith(("*", ":", "#")):
            add_text(stripped.lstrip("*:# ").strip())

    return entries[:8]


PARSERS: dict[str, Callable[..., list[str]]] = {
    "wikiquote": extract_wikiquote_lines,
    "wikisource": extract_wikisource_passages,
    "wiktionary": extract_wiktionary_entries,
}


def _kind_for_category(category: str) -> WorkKind:
    lowered = category.lower()
    if "мульт" in lowered or "animated" in lowered or "cartoon" in lowered:
        return WorkKind.cartoon
    if "литерат" in lowered or "literature" in lowered:
        return WorkKind.book
    if "послов" in lowered or "proverb" in lowered or "поговор" in lowered:
        return WorkKind.proverb_collection
    if "сказ" in lowered or "fairy" in lowered:
        return WorkKind.fairy_tale
    if "песн" in lowered or "song" in lowered:
        return WorkKind.song
    if "film" in lowered or "фильм" in lowered:
        return WorkKind.film
    return WorkKind.other


def _fragment_type_for_category(category: str) -> FragmentType | None:
    lowered = category.lower()
    if "послов" in lowered or "proverb" in lowered or "поговор" in lowered:
        return FragmentType.proverb
    if "афор" in lowered or "aphor" in lowered:
        return FragmentType.aphorism
    if "сказ" in lowered or "fairy" in lowered:
        return FragmentType.fairy_formula
    if "песн" in lowered or "song" in lowered:
        return FragmentType.song_lyric
    return None


def run_mediawiki_ingest(
    db: Session,
    source_key: str,
    *,
    max_pages: int = 150,
    max_items_per_page: int = 40,
    pull_log: PullLog | None = None,
) -> dict[str, int]:
    """Ingest fragments from a configured MediaWiki source."""
    config = load_mediawiki_config(source_key)
    api_url = config["api_url"]
    wiki_base = config.get("wiki_base", api_url.replace("/w/api.php", ""))
    source_site = config.get("source_site", source_key.replace("_", "."))
    language = config.get("language", "ru")
    tier = int(config.get("tier", 1 if language == "ru" else 2))
    parser_name = config.get("parser", "wikiquote")
    parser = PARSERS.get(parser_name, extract_wikiquote_lines)
    default_work_kind = WorkKind(config.get("default_work_kind", "other"))
    default_fragment_type = FragmentType(
        config.get("default_fragment_type", "quote"),
    )
    license_hint = config.get("license_hint", "CC-BY-SA-4.0")
    tag = config.get("tag", source_key)

    stats = {
        "created": 0,
        "merged": 0,
        "skipped": 0,
        "pull_skipped": 0,
        "total_processed": 0,
    }
    logger.info(
        "mediawiki.ingest_begin",
        source=source_key,
        max_pages=max_pages,
        categories=len(config.get("categories", [])),
    )

    with ScraperClient() as client:
        for category in config.get("categories", []):
            logger.info(
                "mediawiki.category_start",
                source=source_key,
                category=category,
            )
            try:
                titles = _category_members(
                    client,
                    api_url,
                    category,
                    max_pages,
                    pull_log=pull_log,
                    source=source_key,
                    stats=stats,
                )
            except Exception as exc:
                on_error(
                    exc,
                    "mediawiki.category_failed",
                    source=source_key,
                    category=category,
                )
                stats["skipped"] += 1
                continue

            work_kind = _kind_for_category(category)
            if work_kind == WorkKind.other:
                work_kind = default_work_kind
            fragment_type = (
                _fragment_type_for_category(category) or default_fragment_type
            )

            for title in titles:
                try:
                    wikitext = _page_wikitext(
                        client,
                        api_url,
                        title,
                        pull_log=pull_log,
                        source=source_key,
                    )
                except Exception as exc:
                    on_error(
                        exc,
                        "mediawiki.page_failed",
                        source=source_key,
                        title=title,
                    )
                    stats["skipped"] += 1
                    continue
                if wikitext is None:
                    stats["pull_skipped"] += 1
                    continue

                if parser_name == "wiktionary":
                    items = parser(title, wikitext)
                elif parser_name == "wikisource":
                    items = parser(wikitext, limit=max_items_per_page)
                else:
                    items = parser(wikitext)[:max_items_per_page]

                if not items:
                    stats["skipped"] += 1
                    continue

                work = get_or_create_work(
                    db,
                    title=title,
                    kind=work_kind,
                    language=language,
                    tier=tier,
                    external_slug=f"{source_key}-{title[:80]}",
                )
                page_url = f"{wiki_base.rstrip('/')}/{quote(title, safe='')}"

                for item_text in items:
                    _, created = upsert_fragment(
                        db,
                        text=item_text,
                        language=language,
                        fragment_type=fragment_type,
                        source_site=source_site,
                        source_url=page_url,
                        external_id=f"{title}:{item_text[:40]}",
                        license_hint=license_hint,
                        work=work,
                        tags=[tag],
                    )
                    stats["total_processed"] += 1
                    if created:
                        stats["created"] += 1
                    else:
                        stats["merged"] += 1

                    processed = (
                        stats["created"] + stats["merged"] + stats["skipped"]
                    )
                    if processed % 10 == 0:
                        logger.info(
                            "mediawiki.progress",
                            source=source_key,
                            **stats,
                        )
                    maybe_commit_batch(
                        db,
                        processed,
                        step=source_key,
                    )

    db.commit()
    logger.info("mediawiki.ingest_complete", source=source_key, **stats)
    return stats
