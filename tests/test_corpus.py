"""Tests for corpus config and review helpers."""

from scrapers.corpus import ingest_defaults
from scrapers.ingest import tier_for_language


def test_corpus_target_is_100k() -> None:
    defaults = ingest_defaults()
    assert defaults["target_total"] == 100000
    assert defaults["citaty_max"] >= 10000


def test_tier_for_language() -> None:
    assert tier_for_language("ru") == 1
    assert tier_for_language("en") == 2
    assert tier_for_language("en", explicit=1) == 1
