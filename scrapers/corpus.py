"""Corpus target and ingest budget configuration."""

from pathlib import Path
from typing import Any

import yaml

_CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "corpus.yaml"


def load_corpus_config() -> dict[str, Any]:
    """Load corpus targets from data/corpus.yaml."""
    with _CORPUS_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ingest_defaults() -> dict[str, int]:
    """Default CLI/pipeline limits aligned with 50k target."""
    cfg = load_corpus_config()
    budgets = cfg.get("budgets", {})
    return {
        "citaty_max": int(budgets.get("citaty_info", 15000)),
        "culture_max": int(budgets.get("culture_ru", 12000)),
        "anekdot_max": int(budgets.get("anekdot_ru", 5000)),
        "wikisource_ru_max_pages": int(budgets.get("wikisource_ru_pages", 200)),
        "wiktionary_ru_max_pages": int(budgets.get("wiktionary_ru_pages", 150)),
        "wikiquote_ru_max_pages": int(budgets.get("wikiquote_ru_pages", 350)),
        "wikiquote_en_max_pages": int(budgets.get("wikiquote_en_pages", 400)),
        "wikisource_en_max_pages": int(budgets.get("wikisource_en_pages", 100)),
        "poetrydb_max": int(budgets.get("poetrydb", 2500)),
        "gutenberg_max": int(budgets.get("gutenberg", 2000)),
        "quotable_max": int(budgets.get("quotable", 800)),
        "opensubtitles_max": int(budgets.get("opensubtitles", 1500)),
        "ruscorpora_max": int(budgets.get("ruscorpora", 2000)),
        "pushdom_max": int(budgets.get("pushdom", 1000)),
        "culture_pages": int(cfg.get("culture_pages", 40)),
        "anekdot_pages": int(cfg.get("anekdot_pages", 80)),
        "target_total": int(cfg.get("target_total", 100000)),
    }
