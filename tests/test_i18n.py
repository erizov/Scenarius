from app.i18n import normalize_ui_lang, translate, ui_context


def test_ui_lang_normalization() -> None:
    assert normalize_ui_lang("en") == "en"
    assert normalize_ui_lang("de") == "ru"


def test_translate_ru_en() -> None:
    assert translate("ru", "search_button") == "Найти"
    assert translate("en", "search_button") == "Search"


def test_ui_context() -> None:
    ctx = ui_context("en")
    assert ctx["ui_lang"] == "en"
    assert "subtitle" in ctx["t"]
