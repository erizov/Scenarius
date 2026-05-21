"""Tests for citaty.info link extraction."""

from scrapers.citaty_info import extract_quote_links, extract_work_links

SAMPLE_HTML = """
<a href="https://citaty.info/quote/546857">q1</a>
<a href="/quote/123">q2</a>
<a href="https://citaty.info/movie/foo-bar">m1</a>
<a href="/cartoon/test-slug">c1</a>
<a href="https://citaty.info/animation/vinni-puh">a1</a>
"""


def test_extract_quote_links_absolute_and_relative() -> None:
    links = extract_quote_links(SAMPLE_HTML)
    assert links == {"546857", "123"}


def test_extract_work_links_absolute_and_relative() -> None:
    links = extract_work_links(SAMPLE_HTML)
    assert links == {
        "/movie/foo-bar",
        "/cartoon/test-slug",
        "/animation/vinni-puh",
    }
