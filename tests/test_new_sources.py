"""Tests for culture.ru and anekdot.ru parsers."""

from scrapers.anekdot_ru import extract_feed_texts
from scrapers.culture_ru_parse import (
    extract_em_quotes,
    json_text_paragraphs,
    strip_html,
)

ANEKDOT_HTML = """
<div class="text">Не принимайте законы близко к сердцу.</div>
<div class="text">Слишком коротко</div>
<div class="text">Современные девушки как-то однобоко понимают сказку про Золушку.</div>
"""


def test_strip_html_and_em_quotes() -> None:
    html = "<p>Текст с <em>«цитатой внутри»</em> и <strong>жирным</strong>.</p>"
    assert "цитатой" in strip_html(html)
    quotes = extract_em_quotes(html)
    assert quotes == ["«цитатой внутри»"]


def test_json_text_paragraphs() -> None:
    blocks = [
        {"type": "split"},
        {"type": "text", "text": "<p>Длинный абзац о русской классике.</p>"},
    ]
    paragraphs = json_text_paragraphs(blocks)
    assert paragraphs == ["Длинный абзац о русской классике."]


def test_anekdot_extract_feed_texts() -> None:
    texts = extract_feed_texts(ANEKDOT_HTML)
    assert len(texts) == 2
    assert "Золушку" in texts[1]
