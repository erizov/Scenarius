"""Load ingest source configuration from data/sources.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scrapers.errors import IngestConfigError

_SOURCES_PATH = Path(__file__).resolve().parents[1] / "data" / "sources.yaml"


def load_sources() -> dict[str, Any]:
    """Load the full sources registry."""
    with _SOURCES_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_source(key: str) -> dict[str, Any]:
    """Load one source block; raise KeyError when missing."""
    data = load_sources()
    if key not in data:
        raise KeyError(f"Unknown source: {key}")
    return data[key]


def source_enabled(key: str) -> bool:
    """Return whether a source is enabled in sources.yaml."""
    try:
        cfg = load_source(key)
    except KeyError:
        return False
    return bool(cfg.get("enabled", True))


def require_env(value: str | None, *, name: str, source: str) -> str:
    """Fail fast when a required secret or setting is missing."""
    if not value or not value.strip():
        raise IngestConfigError(
            f"{name} is required for {source} (set in .env or disable the source)",
        )
    return value.strip()
