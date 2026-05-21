"""Fail-fast context for ingest pipelines."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

import structlog

logger = structlog.get_logger()

_fail_fast: ContextVar[bool] = ContextVar("fail_fast", default=True)


def fail_fast_enabled() -> bool:
    """Return whether the current ingest should stop on first error."""
    return _fail_fast.get()


@contextmanager
def fail_fast_context(enabled: bool) -> Iterator[None]:
    """Set fail-fast mode for nested ingest calls."""
    token = _fail_fast.set(enabled)
    try:
        yield
    finally:
        _fail_fast.reset(token)


def on_error(
    exc: BaseException,
    event: str,
    **fields: object,
) -> None:
    """Re-raise or log a recoverable ingest error."""
    if fail_fast_enabled():
        raise exc
    logger.warning(event, error=str(exc), **fields)
