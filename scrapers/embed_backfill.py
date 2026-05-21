"""Backfill fragment embeddings for semantic RAG."""

from __future__ import annotations

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Fragment, FragmentEmbedding
from app.services.embeddings import (
    _embeddings_table_exists,
    _get_model,
    reset_embeddings_table_cache,
)

logger = structlog.get_logger()


def _missing_fragment_ids(
    db: Session,
    *,
    force: bool,
    limit: int | None,
) -> list:
    if force:
        stmt = select(Fragment.id).order_by(Fragment.created_at)
    else:
        stmt = (
            select(Fragment.id)
            .outerjoin(
                FragmentEmbedding,
                FragmentEmbedding.fragment_id == Fragment.id,
            )
            .where(FragmentEmbedding.fragment_id.is_(None))
            .order_by(Fragment.created_at)
        )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def _embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    if model is None:
        raise RuntimeError(
            "Embedding model unavailable. Install fastembed: "
            "pip install -e '.[embeddings]'",
        )
    return [vector.tolist() for vector in model.embed(texts)]


def run_embed_backfill(
    db: Session,
    *,
    batch_size: int = 128,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Compute and store embeddings for corpus fragments."""
    if not settings.embedding_enabled:
        raise RuntimeError("EMBEDDING_ENABLED=false in settings")

    reset_embeddings_table_cache()
    if not _embeddings_table_exists(db):
        raise RuntimeError(
            "fragment_embeddings table missing. "
            "Install pgvector and run: alembic upgrade head",
        )

    ids = _missing_fragment_ids(db, force=force, limit=limit)
    total = len(ids)
    if total == 0:
        return {"processed": 0, "skipped": 0, "total_pending": 0}

    processed = 0
    for offset in range(0, total, batch_size):
        batch_ids = ids[offset : offset + batch_size]
        fragments = db.scalars(
            select(Fragment).where(Fragment.id.in_(batch_ids)),
        ).all()
        by_id = {item.id: item for item in fragments}
        ordered = [by_id[item_id] for item_id in batch_ids if item_id in by_id]
        if not ordered:
            continue

        vectors = _embed_texts([item.text for item in ordered])
        for fragment, vector in zip(ordered, vectors, strict=True):
            existing = db.get(FragmentEmbedding, fragment.id)
            if existing is None:
                db.add(
                    FragmentEmbedding(
                        fragment_id=fragment.id,
                        embedding=vector,
                        model_name=settings.embedding_model,
                    ),
                )
            else:
                existing.embedding = vector
                existing.model_name = settings.embedding_model
        db.commit()
        processed += len(ordered)
        logger.info(
            "embeddings.backfill_progress",
            processed=processed,
            total=total,
        )

    count = db.scalar(text("SELECT COUNT(*) FROM fragment_embeddings")) or 0
    return {
        "processed": processed,
        "skipped": total - processed,
        "total_embeddings": int(count),
    }
