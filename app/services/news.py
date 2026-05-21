"""Extract news text from raw input or article URLs."""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from app.config import settings

logger = structlog.get_logger()

MAX_TEXT_LEN = 4000
MIN_BODY_LEN = 80
BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


@dataclass
class NewsContent:
    """Normalized news payload for generation."""

    title: str
    body: str
    source_url: str | None = None


class NewsInputError(ValueError):
    """Invalid or blocked news input."""


def normalize_text(value: str) -> NewsContent:
    """Trim and cap pasted news text."""
    body = re.sub(r"\s+", " ", value.strip())
    if len(body) < MIN_BODY_LEN:
        raise NewsInputError("News text is too short")
    if len(body) > MAX_TEXT_LEN:
        body = body[:MAX_TEXT_LEN].rsplit(" ", 1)[0]
    title = body[:120].strip()
    if len(body) > 120:
        title = f"{title}..."
    return NewsContent(title=title, body=body)


def _is_blocked_host(host: str) -> bool:
    lowered = host.lower().strip("[]")
    if lowered in BLOCKED_HOSTS:
        return True
    if lowered.endswith(".local") or lowered.endswith(".internal"):
        return True
    try:
        infos = socket.getaddrinfo(lowered, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def validate_public_url(url: str) -> str:
    """Validate URL scheme/host before fetching."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise NewsInputError("Only http(s) URLs are allowed")
    if not parsed.netloc:
        raise NewsInputError("Invalid URL")
    host = parsed.hostname or ""
    if _is_blocked_host(host):
        raise NewsInputError("URL host is not allowed")
    return url.strip()


def _extract_article(html: str, source_url: str) -> NewsContent:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    paragraphs: list[str] = []
    article = soup.find("article")
    nodes = article.find_all("p") if article else soup.find_all("p")
    for node in nodes:
        text = node.get_text(" ", strip=True)
        if len(text) >= 40:
            paragraphs.append(text)

    body = " ".join(paragraphs)
    if len(body) < MIN_BODY_LEN:
        body = soup.get_text(" ", strip=True)
        body = re.sub(r"\s+", " ", body)

    if len(body) < MIN_BODY_LEN:
        raise NewsInputError("Could not extract enough text from URL")

    if len(body) > MAX_TEXT_LEN:
        body = body[:MAX_TEXT_LEN].rsplit(" ", 1)[0]

    if not title:
        title = body[:120]
    return NewsContent(title=title, body=body, source_url=source_url)


def fetch_news_url(url: str, *, client: httpx.Client | None = None) -> NewsContent:
    """Fetch and extract news article text from a public URL."""
    safe_url = validate_public_url(url)
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=20.0,
            follow_redirects=True,
        )
    try:
        response = client.get(safe_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "<html" not in response.text[:200].lower():
            raise NewsInputError("URL did not return HTML content")
        return _extract_article(response.text, safe_url)
    except httpx.HTTPError as exc:
        logger.warning("news.fetch_failed", url=safe_url, error=str(exc))
        raise NewsInputError(f"Failed to fetch URL: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def resolve_news_input(
    *,
    url: str | None = None,
    text: str | None = None,
) -> NewsContent:
    """Resolve news from URL or pasted text."""
    has_url = bool(url and url.strip())
    has_text = bool(text and text.strip())
    if has_url and has_text:
        raise NewsInputError("Provide either url or text, not both")
    if not has_url and not has_text:
        raise NewsInputError("Provide url or text")
    if has_text:
        return normalize_text(text or "")
    return fetch_news_url(url or "")
