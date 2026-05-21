"""Shared helpers for culture.ru JSON/HTML parsing."""

from __future__ import annotations

import re

TAG_RE = re.compile(r"<[^>]+>")
EM_RE = re.compile(r"<em>(.*?)</em>", re.IGNORECASE | re.DOTALL)
WS_RE = re.compile(r"\s+")


def strip_html(value: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = TAG_RE.sub("", value)
    text = text.replace("\xa0", " ")
    return WS_RE.sub(" ", text).strip()


def extract_em_quotes(html_text: str) -> list[str]:
    """Pull emphasized passages often used as citations."""
    quotes: list[str] = []
    for match in EM_RE.findall(html_text):
        clean = strip_html(match)
        if len(clean) >= 10:
            quotes.append(clean)
    return quotes


def json_text_paragraphs(json_text: list[dict]) -> list[str]:
    """Extract readable paragraphs from culture.ru jsonText blocks."""
    paragraphs: list[str] = []
    for part in json_text or []:
        if part.get("type") != "text":
            continue
        raw = part.get("text") or ""
        clean = strip_html(raw)
        if len(clean) >= 25:
            paragraphs.append(clean)
    return paragraphs


def split_poem_stanzas(text: str) -> list[str]:
    """Split poem text into stanzas for fragment storage."""
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    if len(chunks) <= 1 and len(text) >= 25:
        return [text.strip()]
    return [chunk for chunk in chunks if len(chunk) >= 15]
