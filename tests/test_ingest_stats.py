"""Tests for ingestion stats formatting."""

from scrapers.ingest_stats import IngestTotals, format_totals


def test_format_totals_includes_core_sections() -> None:
    totals = IngestTotals(
        fragments=42,
        languages={"ru": 30, "en": 12},
        people=5,
        authors=3,
        works=10,
        sources={"citaty.info": 25, "wikiquote.ru": 17},
        recent_fragments=4,
    )
    text = format_totals(totals, recent_minutes=5)
    assert "Fragments : 42" in text
    assert "ru      : 30" in text
    assert "en      : 12" in text
    assert "Authors   : 3" in text
    assert "citaty.info" in text
