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
        "nav_comment": "Комментарий",
        "comment_subtitle": "Ироничный комментарий к новости на языке корпуса",
        "comment_button": "Комментировать",
        "comment_hint": "Вставьте ссылку или текст — мы подберём цитаты из корпуса и сгенерируем комментарий.",
        "advanced_formats": "Другой формат",
        "format_comment": "Комментарий",
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
        "placeholder_hint": "Минимум 80 символов текста. Выберите «Текст» или «Ссылка», затем формат.",
        "loading_rag": "Подбор цитат из корпуса и генерация…",
        "diag_title": "Диагностика",
        "diag_format": "Формат",
        "diag_rag": "Цитат RAG",
        "diag_llm": "LLM",
        "diag_no_citations": "RAG не нашёл цитат — проверьте ingest и pgvector.",
        "error_llm_hint": "Запустите Ollama (ollama serve) или задайте OPENAI_API_KEY в .env.",
        "error_input_hint": "Переключитесь на «Текст» и вставьте новость (≥80 символов).",
        "error_client_short": "Текст слишком короткий (нужно минимум 80 символов).",
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
        "nav_comment": "Comment",
        "comment_subtitle": "Ironic news commentary grounded in the corpus",
        "comment_button": "Comment",
        "comment_hint": "Paste a link or text — we match corpus quotes and generate commentary.",
        "advanced_formats": "Other format",
        "format_comment": "Commentary",
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
        "placeholder_hint": "At least 80 characters. Pick Text or Link, then a format.",
        "loading_rag": "Matching corpus quotes and generating…",
        "diag_title": "Diagnostics",
        "diag_format": "Format",
        "diag_rag": "RAG quotes",
        "diag_llm": "LLM",
        "diag_no_citations": "RAG found no citations — run ingest and check pgvector.",
        "error_llm_hint": "Start Ollama (ollama serve) or set OPENAI_API_KEY in .env.",
        "error_input_hint": "Switch to Text and paste the news (≥80 characters).",
        "error_client_short": "Text is too short (minimum 80 characters).",
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
