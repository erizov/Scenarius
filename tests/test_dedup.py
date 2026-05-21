from scrapers.dedup import normalize_text, text_fingerprint


def test_fingerprint_stable() -> None:
    a = text_fingerprint("Надо, Федя, надо!", "ru")
    b = text_fingerprint("  надо федя надо ", "ru")
    assert a == b


def test_fingerprint_diff_language() -> None:
    ru = text_fingerprint("Hello world", "ru")
    en = text_fingerprint("Hello world", "en")
    assert ru != en


def test_normalize_strips_punctuation() -> None:
    assert normalize_text("«Привет!»") == "привет"
