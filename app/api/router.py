import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    FragmentListOut,
    FragmentMatchRequest,
    FragmentOut,
    FragmentSampleRequest,
)
from app.services import fragments as fragment_service

router = APIRouter(prefix="/api/v1", tags=["fragments"])


@router.get("/fragments", response_model=FragmentListOut)
def list_fragments(
    q: str | None = Query(default=None, min_length=1),
    language: str | None = None,
    fragment_type: str | None = None,
    tier: int | None = Query(default=None, ge=1, le=2),
    verified_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> FragmentListOut:
    """List fragments with optional filters."""
    rows, total = fragment_service.list_fragments(
        db,
        q=q,
        language=language,
        fragment_type=fragment_type,
        tier=tier,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )
    items = [
        FragmentOut.model_validate(fragment_service.fragment_to_dict(row))
        for row in rows
    ]
    return FragmentListOut(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/fragments/{fragment_id}", response_model=FragmentOut)
def get_fragment(
    fragment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FragmentOut:
    """Return a single fragment."""
    row = fragment_service.get_fragment(db, fragment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return FragmentOut.model_validate(fragment_service.fragment_to_dict(row))


@router.post("/fragments/match", response_model=list[FragmentOut])
def match_fragments(
    body: FragmentMatchRequest,
    db: Session = Depends(get_db),
) -> list[FragmentOut]:
    """Match fragments to a news or script context."""
    rows = fragment_service.match_fragments(
        db,
        context=body.context,
        language=body.language,
        tier=body.tier,
        limit=body.limit,
        mode=body.mode,
    )
    return [
        FragmentOut.model_validate(fragment_service.fragment_to_dict(row))
        for row in rows
    ]


@router.post("/fragments/sample", response_model=list[FragmentOut])
def sample_fragments(
    body: FragmentSampleRequest,
    db: Session = Depends(get_db),
) -> list[FragmentOut]:
    """Sample random fragments for script generation."""
    rows = fragment_service.sample_fragments(
        db,
        work_kind=body.work_kind,
        language=body.language,
        tier=body.tier,
        tags=body.tags,
        include_dialogues=body.include_dialogues,
        limit=body.limit,
    )
    return [
        FragmentOut.model_validate(fragment_service.fragment_to_dict(row))
        for row in rows
    ]


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
