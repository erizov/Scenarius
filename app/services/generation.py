"""Generate short stories from news using corpus RAG."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.services import fragments as fragment_service
from app.services.llm import LLMResult, LLMUnavailableError, generate_text
from app.services.news import NewsContent, NewsInputError, resolve_news_input

logger = structlog.get_logger()

STORY_FORMATS = frozenset({"comment", "parable", "fairy_tale", "anecdote", "story"})

FORMAT_RETRIEVAL: dict[str, dict[str, Any]] = {
    "comment": {
        "sample_types": ["aphorism", "proverb", "quote"],
        "work_kind": None,
        "include_dialogues": True,
    },
    "parable": {
        "sample_types": ["proverb", "aphorism"],
        "work_kind": "proverb_collection",
        "include_dialogues": False,
    },
    "fairy_tale": {
        "sample_types": ["fairy_formula", "quote"],
        "work_kind": "fairy_tale",
        "include_dialogues": False,
    },
    "anecdote": {
        "sample_types": ["aphorism", "quote"],
        "work_kind": "other",
        "include_dialogues": False,
        "tags": ["анекдот"],
    },
    "story": {
        "sample_types": ["dialogue", "quote"],
        "work_kind": "film",
        "include_dialogues": True,
    },
}

FORMAT_LABELS = {
    "ru": {
        "comment": "комментарий",
        "parable": "притча",
        "fairy_tale": "сказка",
        "anecdote": "анекдот",
        "story": "история",
    },
    "en": {
        "comment": "commentary",
        "parable": "parable",
        "fairy_tale": "fairy tale",
        "anecdote": "anecdote",
        "story": "short story",
    },
}


@dataclass
class StoryCitation:
    """Corpus fragment used as RAG context."""

    id: uuid.UUID
    text: str
    fragment_type: str
    work_title: str | None


@dataclass
class StoryResult:
    """Generated story payload."""

    story: str
    format: str
    language: str
    news_title: str
    news_source_url: str | None
    citations: list[StoryCitation]
    provider: str
    model: str


def _dedupe_fragments(rows: list) -> list:
    seen: set[uuid.UUID] = set()
    unique = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        unique.append(row)
    return unique


def _retrieve_fragments(
    db: Session,
    *,
    news: NewsContent,
    story_format: str,
    language: str,
) -> list:
    """Semantic match + style sample for the chosen format."""
    cfg = FORMAT_RETRIEVAL[story_format]
    tier = [1] if language == "ru" else [1, 2]
    matched = fragment_service.match_fragments(
        db,
        context=news.body,
        language=language,
        tier=tier,
        limit=8,
        mode="semantic",
    )
    sampled = fragment_service.sample_fragments(
        db,
        work_kind=cfg.get("work_kind"),
        language=language,
        tier=tier,
        tags=cfg.get("tags"),
        include_dialogues=cfg.get("include_dialogues", True),
        limit=5,
    )
    return _dedupe_fragments(matched + sampled)[:10]


def _citation_from_fragment(fragment) -> StoryCitation:
    work_title = fragment.work.title if fragment.work else None
    return StoryCitation(
        id=fragment.id,
        text=fragment.text,
        fragment_type=fragment.fragment_type.value,
        work_title=work_title,
    )


def _build_prompt(
    *,
    news: NewsContent,
    story_format: str,
    language: str,
    citations: list[StoryCitation],
) -> str:
    label = FORMAT_LABELS[language][story_format]
    corpus_lines = []
    for index, item in enumerate(citations, start=1):
        source = item.work_title or "corpus"
        corpus_lines.append(f"[{index}] ({source}) {item.text}")

    corpus_block = "\n".join(corpus_lines) if corpus_lines else "(no corpus matches)"

    if story_format == "comment":
        if language == "ru":
            return (
                "Напиши ироничный культурный комментарий к новости "
                "(2–4 предложения).\n"
                "Опирайся на тон и образы цитат корпуса, без дословного "
                "копирования. Один острый вывод.\n\n"
                f"Новость: {news.title}\n{news.body}\n\n"
                f"Корпус:\n{corpus_block}\n\n"
                "Ответ — только текст комментария, без заголовков."
            )
        return (
            "Write an ironic cultural commentary on the news "
            "(2–4 sentences).\n"
            "Echo the tone of the corpus quotes without copying them "
            "verbatim. One sharp takeaway.\n\n"
            f"News: {news.title}\n{news.body}\n\n"
            f"Corpus:\n{corpus_block}\n\n"
            "Reply with only the commentary text, no headings."
        )

    if language == "ru":
        return (
            f"Напиши короткую {label} (150–300 слов) по мотивам новости.\n"
            "Используй тон и образы из цитат корпуса, но не копируй их дословно.\n"
            "Один ясный вывод или punchline в конце.\n\n"
            f"Новость: {news.title}\n{news.body}\n\n"
            f"Корпус:\n{corpus_block}\n\n"
            f"Ответ — только текст {label}, без заголовков и пояснений."
        )

    return (
        f"Write a short {label} (150–300 words) inspired by the news.\n"
        "Echo the tone of the corpus quotes without copying them verbatim.\n"
        "End with one clear moral or punchline.\n\n"
        f"News: {news.title}\n{news.body}\n\n"
        f"Corpus:\n{corpus_block}\n\n"
        f"Reply with only the {label} text, no headings or commentary."
    )


def generate_story(
    db: Session,
    *,
    url: str | None = None,
    text: str | None = None,
    story_format: str,
    language: str,
) -> StoryResult:
    """End-to-end news → RAG → LLM story generation."""
    if story_format not in STORY_FORMATS:
        raise ValueError(f"Unsupported format: {story_format}")

    news = resolve_news_input(url=url, text=text)
    fragments = _retrieve_fragments(
        db,
        news=news,
        story_format=story_format,
        language=language,
    )
    citations = [_citation_from_fragment(item) for item in fragments]
    prompt = _build_prompt(
        news=news,
        story_format=story_format,
        language=language,
        citations=citations,
    )

    try:
        llm: LLMResult = generate_text(prompt)
    except LLMUnavailableError:
        logger.warning("generation.llm_unavailable")
        raise

    return StoryResult(
        story=llm.text,
        format=story_format,
        language=language,
        news_title=news.title,
        news_source_url=news.source_url,
        citations=citations,
        provider=llm.provider,
        model=llm.model,
    )
