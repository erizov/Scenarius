"""Embedding generation and pgvector storage."""

from __future__ import annotations

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Fragment, FragmentEmbedding

logger = structlog.get_logger()

_model = None


def _get_model():
    """Lazy-load fastembed model."""
    global _model
    if _model is not None:
        return _model
    if not settings.embedding_enabled:
        return None
    try:
        from fastembed import TextEmbedding
    except ImportError:
        logger.warning("embeddings.fastembed_missing")
        return None
    try:
        _model = TextEmbedding(model_name=settings.embedding_model)
    except ValueError as exc:
        logger.warning("embeddings.unsupported_model", error=str(exc))
        return None
    return _model


def embed_text(value: str) -> list[float] | None:
    """Generate embedding vector for text."""
    model = _get_model()
    if model is None:
        return None
    vectors = list(model.embed([value]))
    if not vectors:
        return None
    return vectors[0].tolist()


_embeddings_table_available: bool | None = None


def reset_embeddings_table_cache() -> None:
    """Clear cached pgvector table probe (after migrations)."""
    global _embeddings_table_available
    _embeddings_table_available = None


def _embeddings_table_exists(db: Session) -> bool:
    """Return True when fragment_embeddings exists (pgvector migrated)."""
    global _embeddings_table_available
    if _embeddings_table_available is not None:
        return _embeddings_table_available
    exists = db.execute(
        text("SELECT to_regclass('public.fragment_embeddings') IS NOT NULL"),
    ).scalar()
    _embeddings_table_available = bool(exists)
    return _embeddings_table_available


def upsert_embedding(db: Session, fragment: Fragment) -> None:
    """Store embedding for a fragment."""
    if not _embeddings_table_exists(db):
        return
    vector = embed_text(fragment.text)
    if vector is None:
        return
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


def semantic_match(
    db: Session,
    *,
    context: str,
    language: str = "ru",
    tier: list[int] | None = None,
    limit: int = 5,
) -> list[Fragment]:
    """Find fragments by cosine similarity via pgvector."""
    if not _embeddings_table_exists(db):
        logger.info("embeddings.table_missing", fallback="keyword")
        return []

    vector = embed_text(context)
    if vector is None:
        return []

    vector_str = "[" + ",".join(str(v) for v in vector) + "]"
    tier_clause = ""
    params: dict = {
        "embedding": vector_str,
        "language": language,
        "limit": limit,
    }
    if tier:
        tier_clause = "AND (w.tier IS NULL OR w.tier = ANY(:tiers))"
        params["tiers"] = tier

    sql = text(
        f"""
        SELECT f.id
        FROM fragments f
        JOIN fragment_embeddings fe ON fe.fragment_id = f.id
        LEFT JOIN works w ON w.id = f.work_id
        WHERE f.language = :language
        AND (
            f.meta->>'review_status' IS NULL
            OR f.meta->>'review_status' != 'rejected'
        )
        {tier_clause}
        ORDER BY fe.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )
    rows = db.execute(sql, params).all()
    if not rows:
        return []

    ids = [row[0] for row in rows]
    fragments = db.scalars(
        select(Fragment).where(Fragment.id.in_(ids)),
    ).all()
    by_id = {item.id: item for item in fragments}
    return [by_id[item_id] for item_id in ids if item_id in by_id]
