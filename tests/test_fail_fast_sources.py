"""Tests for fail-fast ingest behavior and new source parsers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scrapers.errors import IngestConfigError
from scrapers.fail_fast import fail_fast_context, fail_fast_enabled, on_error
from scrapers.gutenberg import extract_gutenberg_passages
from scrapers.opensubtitles import run_opensubtitles
from scrapers.pushdom import run_pushdom
from scrapers.ruscorpora import run_ruscorpora
from scrapers.sources import source_enabled
from scrapers.srt_parse import extract_srt_lines


GUTENBERG_SAMPLE = """
*** START OF THE PROJECT GUTENBERG EBOOK SAMPLE ***
First paragraph with enough characters to ingest.

Second paragraph also long enough for the corpus pipeline.
*** END OF THE PROJECT GUTENBERG EBOOK SAMPLE ***
"""

SRT_SAMPLE = """
1
00:00:01,000 --> 00:00:04,000
Hello there, Neo.

2
00:00:05,000 --> 00:00:08,000
Follow the white rabbit.
"""


def test_extract_gutenberg_passages() -> None:
    passages = extract_gutenberg_passages(GUTENBERG_SAMPLE, limit=5)
    assert len(passages) == 2
    assert "First paragraph" in passages[0]


def test_extract_srt_lines() -> None:
    lines = extract_srt_lines(SRT_SAMPLE)
    assert lines == [
        "Hello there, Neo.",
        "Follow the white rabbit.",
    ]


def test_fail_fast_context_raises() -> None:
    assert fail_fast_enabled() is True
    with fail_fast_context(True):
        with pytest.raises(RuntimeError):
            on_error(RuntimeError("boom"), "test.event")


def test_fail_fast_context_logs_when_disabled() -> None:
    with fail_fast_context(False):
        assert fail_fast_enabled() is False
        on_error(ValueError("soft"), "test.soft")
    assert fail_fast_enabled() is True


def test_optional_sources_disabled_by_default() -> None:
    assert source_enabled("poetrydb") is True
    assert source_enabled("gutenberg") is True
    assert source_enabled("quotable") is False
    assert source_enabled("opensubtitles") is False
    assert source_enabled("ruscorpora") is False
    assert source_enabled("pushdom") is False


def test_opensubtitles_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scrapers.opensubtitles.source_enabled",
        lambda _key: True,
    )
    monkeypatch.setattr(
        "scrapers.opensubtitles.settings.opensubtitles_api_key",
        "",
    )
    with pytest.raises(IngestConfigError, match="OPENSUBTITLES_API_KEY"):
        run_opensubtitles(MagicMock(), max_items=1)


def test_pushdom_requires_datasets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scrapers.pushdom.source_enabled",
        lambda _key: True,
    )
    with pytest.raises(IngestConfigError, match="pushdom.datasets"):
        run_pushdom(MagicMock(), max_items=1)


def test_ruscorpora_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scrapers.ruscorpora.source_enabled",
        lambda _key: True,
    )
    monkeypatch.setattr(
        "scrapers.ruscorpora.settings.ruscorpora_api_key",
        "",
    )
    with pytest.raises(IngestConfigError, match="RUSCORPORA_API_KEY"):
        run_ruscorpora(MagicMock(), max_items=1)
