"""Tests for news input extraction."""

import pytest

from app.services.news import (
    NewsInputError,
    normalize_text,
    validate_public_url,
)


def test_normalize_text_trims_and_titles() -> None:
    body = "А" * 150
    news = normalize_text(f"  {body}  ")
    assert news.title.endswith("...")
    assert len(news.body) >= 80


def test_normalize_text_too_short() -> None:
    with pytest.raises(NewsInputError):
        normalize_text("short")


def test_validate_public_url_blocks_localhost() -> None:
    with pytest.raises(NewsInputError):
        validate_public_url("http://localhost/news")


def test_validate_public_url_allows_https() -> None:
    assert validate_public_url("https://example.com/article") == (
        "https://example.com/article"
    )
