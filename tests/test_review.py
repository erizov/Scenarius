"""Tests for review queue helpers."""

from app.services.review import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    is_scraped,
    public_visibility_filter,
)
from app.models import Fragment, SourceRef


def test_review_constants() -> None:
    assert REVIEW_PENDING == "pending"
    assert REVIEW_APPROVED == "approved"
    assert REVIEW_REJECTED == "rejected"


def test_is_scraped_verified_is_false() -> None:
    fragment = Fragment(verified=True, meta={"review_status": REVIEW_PENDING})
    assert is_scraped(fragment) is False


def test_is_scraped_pending_source() -> None:
    fragment = Fragment(
        verified=False,
        meta={"review_status": REVIEW_PENDING},
        sources=[SourceRef(source_site="citaty.info")],
    )
    assert is_scraped(fragment) is True


def test_public_visibility_filter_builds() -> None:
    clause = public_visibility_filter()
    assert clause is not None
