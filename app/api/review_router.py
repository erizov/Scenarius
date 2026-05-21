"""Review queue API for scraped fragments."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FragmentOut, ReviewActionOut, ReviewListOut
from app.services import fragments as fragment_service
from app.services import review as review_service

router = APIRouter(prefix="/api/v1/review", tags=["review"])


@router.get("/queue", response_model=ReviewListOut)
def review_queue(
    status: str = Query(default=review_service.REVIEW_PENDING),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ReviewListOut:
    """List scraped fragments awaiting human review."""
    rows, total = review_service.list_review_queue(
        db,
        status=status,
        limit=limit,
        offset=offset,
    )
    counts = review_service.count_by_status(db)
    items = [
        FragmentOut.model_validate(fragment_service.fragment_to_dict(row))
        for row in rows
    ]
    return ReviewListOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        pending=counts[review_service.REVIEW_PENDING],
        approved=counts[review_service.REVIEW_APPROVED],
        rejected=counts[review_service.REVIEW_REJECTED],
    )


@router.post("/{fragment_id}/approve", response_model=ReviewActionOut)
def approve_fragment(
    fragment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ReviewActionOut:
    """Approve a scraped fragment for search and scripts."""
    fragment = review_service.approve_fragment(db, fragment_id)
    if fragment is None:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return ReviewActionOut(
        id=fragment.id,
        review_status=fragment.meta.get("review_status", "approved"),
        verified=fragment.verified,
    )


@router.post("/{fragment_id}/reject", response_model=ReviewActionOut)
def reject_fragment(
    fragment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ReviewActionOut:
    """Reject a scraped fragment (hidden from public API)."""
    fragment = review_service.reject_fragment(db, fragment_id)
    if fragment is None:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return ReviewActionOut(
        id=fragment.id,
        review_status=fragment.meta.get("review_status", "rejected"),
        verified=fragment.verified,
    )
