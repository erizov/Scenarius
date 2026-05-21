"""Load canonical works and authors from YAML."""

from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "canonical"


def load_yaml(name: str) -> list[dict[str, Any]]:
    """Load a YAML list from data/canonical/."""
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{name} must contain a YAML list")
    return data


def load_works() -> list[dict[str, Any]]:
    """Return canonical works registry from works*.yaml files."""
    items: list[dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("works*.yaml")):
        items.extend(load_yaml(path.name))
    return items


def load_authors() -> list[dict[str, Any]]:
    """Return canonical authors registry."""
    return load_yaml("authors.yaml")


def load_fragments() -> list[dict[str, Any]]:
    """Return curated canonical fragments from fragments*.yaml files."""
    items: list[dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("fragments*.yaml")):
        items.extend(load_yaml(path.name))
    return items
