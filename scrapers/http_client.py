"""Shared HTTP client for scrapers."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from app.config import settings

if TYPE_CHECKING:
    from scrapers.pull_log import PullLog

logger = structlog.get_logger()

DEFAULT_HEADERS = {
    "User-Agent": settings.scraper_user_agent,
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
}


class ScraperClient:
    """Rate-limited HTTP client with Wikimedia-friendly headers."""

    def __init__(self, *, delay: float | None = None) -> None:
        self._client = httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=settings.scraper_timeout_seconds,
            follow_redirects=True,
        )
        self._delay = (
            settings.scraper_delay_seconds if delay is None else delay
        )

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        raise_for_status: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """GET with polite delay between requests."""
        if self._delay > 0:
            time.sleep(self._delay)
        response = self._client.get(url, params=params, **kwargs)
        if raise_for_status:
            response.raise_for_status()
        return response

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        raise_for_status: bool = True,
        pull_log: PullLog | None = None,
        source: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """GET and parse JSON response."""
        response = self.fetch(
            url,
            params=params,
            raise_for_status=raise_for_status,
            pull_log=pull_log,
            source=source,
            **kwargs,
        )
        if response is None:
            return None
        return response.json()

    def post_json(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        raise_for_status: bool = True,
        pull_log: PullLog | None = None,
        source: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """POST JSON and parse JSON response."""
        response = self.fetch_post(
            url,
            json=json,
            raise_for_status=raise_for_status,
            pull_log=pull_log,
            source=source,
            **kwargs,
        )
        if response is None:
            return None
        return response.json()

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        raise_for_status: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """POST with polite delay between requests."""
        if self._delay > 0:
            time.sleep(self._delay)
        response = self._client.post(url, json=json, **kwargs)
        if raise_for_status:
            response.raise_for_status()
        return response

    def fetch_post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        raise_for_status: bool = True,
        pull_log: PullLog | None = None,
        source: str = "",
        **kwargs: Any,
    ) -> httpx.Response | None:
        """POST with optional pull-log skip and persistence."""
        key = None
        if pull_log is not None:
            from scrapers.pull_log import make_pull_key

            body_key = json.dumps(json, sort_keys=True) if json else ""
            key = make_pull_key(url, {"post": body_key})
            if pull_log.should_skip(key):
                return None
        try:
            response = self.post(
                url,
                json=json,
                raise_for_status=raise_for_status,
                **kwargs,
            )
        except Exception as exc:
            if pull_log is not None and key is not None:
                pull_log.record_failure(key, source, str(exc))
            raise
        if pull_log is not None and key is not None:
            pull_log.record_success(key, source)
        return response

    def fetch(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        raise_for_status: bool = True,
        pull_log: PullLog | None = None,
        source: str = "",
        **kwargs: Any,
    ) -> httpx.Response | None:
        """GET with optional pull-log skip and persistence."""
        key = None
        if pull_log is not None:
            from scrapers.pull_log import make_pull_key

            key = make_pull_key(url, params)
            if pull_log.should_skip(key):
                return None
        try:
            response = self.get(
                url,
                params=params,
                raise_for_status=raise_for_status,
                **kwargs,
            )
        except Exception as exc:
            if pull_log is not None and key is not None:
                pull_log.record_failure(key, source, str(exc))
            raise
        if pull_log is not None and key is not None:
            pull_log.record_success(key, source)
        return response

    def close(self) -> None:
        """Close underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "ScraperClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
