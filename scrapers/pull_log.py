"""Persistent log of scraper HTTP pulls for resume/skip on reruns."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode, urlparse, urlunparse

PullStatus = Literal["success", "failure"]

DEFAULT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "ingest_pull_log.json"
)
FLUSH_EVERY = 25


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def make_pull_key(url: str, params: dict[str, Any] | None = None) -> str:
    """Build a stable key for a GET request."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    query_items: list[tuple[str, str]] = []
    if params:
        for key, value in sorted(params.items()):
            query_items.append((str(key), str(value)))
    query_items.sort()
    query = urlencode(query_items)
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            query,
            "",
        ),
    )
    return normalized


class PullLog:
    """Track successful and failed HTTP pulls between ingest runs."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        enabled: bool = True,
    ) -> None:
        self.path = path or DEFAULT_PATH
        self.enabled = enabled
        self._records: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._writes_since_flush = 0
        self.session_skipped = 0
        self.session_success = 0
        self.session_failure = 0
        if self.enabled:
            self.load()

    def load(self) -> None:
        """Load records from disk."""
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        urls = payload.get("urls")
        if isinstance(urls, dict):
            self._records = urls

    def save(self) -> None:
        """Persist records to disk."""
        if not self.enabled or not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": _utc_now(),
            "urls": self._records,
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._dirty = False
        self._writes_since_flush = 0

    def should_skip(self, key: str) -> bool:
        """Return True when a prior successful pull should be skipped."""
        if not self.enabled:
            return False
        record = self._records.get(key)
        if record and record.get("status") == "success":
            self.session_skipped += 1
            return True
        return False

    def record_success(self, key: str, source: str) -> None:
        """Mark a pull as successful."""
        if not self.enabled:
            return
        self._records[key] = {
            "status": "success",
            "source": source,
            "at": _utc_now(),
            "error": None,
        }
        self.session_success += 1
        self._mark_dirty()

    def record_failure(self, key: str, source: str, error: str) -> None:
        """Mark a pull as failed (retried on next run)."""
        if not self.enabled:
            return
        self._records[key] = {
            "status": "failure",
            "source": source,
            "at": _utc_now(),
            "error": error[:500],
        }
        self.session_failure += 1
        self._mark_dirty()

    def summary(self) -> dict[str, int]:
        """Counts for the current session and stored log."""
        stored_success = sum(
            1 for item in self._records.values() if item.get("status") == "success"
        )
        stored_failure = sum(
            1 for item in self._records.values() if item.get("status") == "failure"
        )
        return {
            "pull_log_stored_success": stored_success,
            "pull_log_stored_failure": stored_failure,
            "pull_log_session_skipped": self.session_skipped,
            "pull_log_session_success": self.session_success,
            "pull_log_session_failure": self.session_failure,
        }

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._writes_since_flush += 1
        if self._writes_since_flush >= FLUSH_EVERY:
            self.save()
