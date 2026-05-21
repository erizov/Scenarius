"""Tests for MediaWiki text extractors."""

from scrapers.mediawiki import (
    extract_wikiquote_lines,
    extract_wikisource_passages,
    extract_wiktionary_entries,
)


def test_extract_wikiquote_lines() -> None:
    text = "* «Жизнь прекрасна»\n** nested skip\n* Plain quote here"
    lines = extract_wikiquote_lines(text)
    assert len(lines) == 2
    assert "прекрасна" in lines[0]


def test_extract_wikisource_passages() -> None:
    text = (
        "== Заголовок ==\n"
        "Жила-была царевна в далёком kingdom.\n"
        "<poem>\n"
        "| In the forest deep and wide\n"
        "</poem>\n"
    )
    passages = extract_wikisource_passages(text, limit=5)
    assert any("царевна" in item for item in passages)


def test_extract_wiktionary_entries_uses_title() -> None:
    title = "Тише едешь — дальше будешь"
    text = "== {{=ru=}} ==\n# пословица"
    entries = extract_wiktionary_entries(title, text)
    assert entries[0] == title
