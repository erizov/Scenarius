from scrapers.canonical import load_authors, load_fragments, load_works


def test_canonical_works_load() -> None:
    works = load_works()
    assert len(works) >= 40
    assert works[0]["id"]
    assert works[0]["title"]
    assert works[0]["kind"] in {
        "film",
        "book",
        "poem",
        "cartoon",
        "fairy_tale",
        "proverb_collection",
    }


def test_canonical_authors_load() -> None:
    authors = load_authors()
    assert len(authors) >= 8
    ids = {item["id"] for item in authors}
    assert "gaidai" in ids
    assert "pushkin" in ids


def test_canonical_fragments_load() -> None:
    fragments = load_fragments()
    assert len(fragments) >= 75
    assert fragments[0]["work_id"]
    assert fragments[0]["text"]
    langs = {item["language"] for item in fragments}
    assert "ru" in langs
    assert "en" in langs
