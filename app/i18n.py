"""UI translations for RU/EN toggle."""

from typing import Any

SUPPORTED = ("ru", "en")

STRINGS: dict[str, dict[str, str]] = {
    "ru": {
        "subtitle": "Цитатник для сценариев и комментариев",
        "search_placeholder": "Поиск цитаты...",
        "search_label": "Поиск",
        "language_label": "Язык",
        "type_label": "Тип",
        "all_languages": "Все языки",
        "all_types": "Все типы",
        "search_button": "Найти",
        "records": "записей",
        "empty": "Пока пусто. Запустите seed или ingest.",
        "empty_cmd": "python -m scrapers.cli ingest-all",
        "api_link": "API",
        "type_quote": "Цитата",
        "type_dialogue": "Диалог",
        "type_proverb": "Пословица",
        "type_aphorism": "Афоризм",
        "ui_lang": "Интерфейс",
        "nav_browse": "Корпус",
        "nav_create": "Создать",
        "create_subtitle": "Притча, сказка, анекдот или история по новости",
        "input_mode_url": "Ссылка",
        "input_mode_text": "Текст",
        "news_url_label": "Ссылка на новость",
        "news_url_placeholder": "https://...",
        "news_text_label": "Текст новости",
        "news_text_placeholder": "Вставьте текст новости...",
        "format_label": "Формат",
        "format_parable": "Притча",
        "format_fairy_tale": "Сказка",
        "format_anecdote": "Анекдот",
        "format_story": "История",
        "generate_button": "Создать",
        "generating": "Генерация...",
        "sources_title": "Источники корпуса",
        "provider_label": "Модель",
        "error_title": "Ошибка",
    },
    "en": {
        "subtitle": "Quote corpus for scripts and news commentary",
        "search_placeholder": "Search quotes...",
        "search_label": "Search",
        "language_label": "Language",
        "type_label": "Type",
        "all_languages": "All languages",
        "all_types": "All types",
        "search_button": "Search",
        "records": "records",
        "empty": "Empty corpus. Run seed or ingest.",
        "empty_cmd": "python -m scrapers.cli ingest-all",
        "api_link": "API",
        "type_quote": "Quote",
        "type_dialogue": "Dialogue",
        "type_proverb": "Proverb",
        "type_aphorism": "Aphorism",
        "ui_lang": "UI",
        "nav_browse": "Corpus",
        "nav_create": "Create",
        "create_subtitle": "Parable, fairy tale, anecdote, or story from news",
        "input_mode_url": "Link",
        "input_mode_text": "Text",
        "news_url_label": "News URL",
        "news_url_placeholder": "https://...",
        "news_text_label": "News text",
        "news_text_placeholder": "Paste news text...",
        "format_label": "Format",
        "format_parable": "Parable",
        "format_fairy_tale": "Fairy tale",
        "format_anecdote": "Anecdote",
        "format_story": "Story",
        "generate_button": "Generate",
        "generating": "Generating...",
        "sources_title": "Corpus sources",
        "provider_label": "Model",
        "error_title": "Error",
    },
}


def normalize_ui_lang(value: str | None) -> str:
    """Return supported UI language code."""
    if value in SUPPORTED:
        return value
    return "ru"


def translate(lang: str, key: str) -> str:
    """Translate a UI string key."""
    code = normalize_ui_lang(lang)
    return STRINGS[code].get(key, STRINGS["ru"].get(key, key))


def ui_context(lang: str) -> dict[str, Any]:
    """Build template context for all UI strings."""
    code = normalize_ui_lang(lang)
    return {
        "ui_lang": code,
        "t": STRINGS[code],
        "supported_langs": SUPPORTED,
    }
