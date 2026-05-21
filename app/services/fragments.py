import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Fragment, FragmentTag, Tag, Work
from app.services.review import public_visibility_filter
from app.services.embeddings import semantic_match


def _fragment_query():
    """Base query with relationships needed for API output."""
    return select(Fragment).options(
        selectinload(Fragment.work),
        selectinload(Fragment.speaker),
        selectinload(Fragment.fragment_tags).selectinload(FragmentTag.tag),
        selectinload(Fragment.sources),
    )


def fragment_to_dict(fragment: Fragment) -> dict:
    """Convert ORM fragment to API-friendly dict."""
    tags = [ft.tag.name for ft in fragment.fragment_tags]
    work = None
    if fragment.work is not None:
        work = {
            "title": fragment.work.title,
            "kind": fragment.work.kind.value,
            "year": fragment.work.year,
            "tier": fragment.work.tier,
            "language": fragment.work.language,
        }
    speaker = None
    if fragment.speaker is not None:
        speaker = {"name": fragment.speaker.name}
    return {
        "id": fragment.id,
        "text": fragment.text,
        "fragment_type": fragment.fragment_type.value,
        "language": fragment.language,
        "verified": fragment.verified,
        "review_status": (fragment.meta or {}).get("review_status"),
        "context": fragment.context,
        "work": work,
        "speaker": speaker,
        "tags": tags,
        "sources": fragment.sources,
    }


def list_fragments(
    db: Session,
    *,
    q: str | None = None,
    language: str | None = None,
    fragment_type: str | None = None,
    tier: int | None = None,
    verified_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Fragment], int]:
    """Search fragments with optional filters."""
    stmt = _fragment_query().where(public_visibility_filter())
    count_stmt = select(func.count()).select_from(Fragment).where(
        public_visibility_filter(),
    )

    if q:
        pattern = f"%{q.strip()}%"
        condition = Fragment.text.ilike(pattern)
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    if language:
        stmt = stmt.where(Fragment.language == language)
        count_stmt = count_stmt.where(Fragment.language == language)

    if fragment_type:
        stmt = stmt.where(Fragment.fragment_type == fragment_type)
        count_stmt = count_stmt.where(Fragment.fragment_type == fragment_type)

    if verified_only:
        stmt = stmt.where(Fragment.verified.is_(True))
        count_stmt = count_stmt.where(Fragment.verified.is_(True))

    if tier is not None:
        stmt = stmt.join(Work, Fragment.work_id == Work.id).where(
            Work.tier == tier,
        )
        count_stmt = count_stmt.join(Work, Fragment.work_id == Work.id).where(
            Work.tier == tier,
        )

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(Fragment.created_at.desc()).limit(limit).offset(offset),
    ).all()
    return list(rows), total


def get_fragment(db: Session, fragment_id: uuid.UUID) -> Fragment | None:
    """Fetch a single fragment by id."""
    return db.scalars(
        _fragment_query().where(Fragment.id == fragment_id),
    ).first()


def match_fragments(
    db: Session,
    *,
    context: str,
    language: str = "ru",
    tier: list[int] | None = None,
    limit: int = 5,
    mode: str = "keyword",
) -> list[Fragment]:
    """Match fragments by semantic or keyword search."""
    if mode == "semantic":
        semantic_rows = semantic_match(
            db,
            context=context,
            language=language,
            tier=tier,
            limit=limit,
        )
        if semantic_rows:
            return semantic_rows

    words = [w for w in context.split() if len(w) >= 3][:8]
    if not words:
        words = [context[:40]]

    conditions = [Fragment.text.ilike(f"%{word}%") for word in words]
    stmt = _fragment_query().where(
        Fragment.language == language,
        public_visibility_filter(),
        or_(*conditions),
    )
    if tier:
        stmt = stmt.join(Work, Fragment.work_id == Work.id).where(
            Work.tier.in_(tier),
        )

    return list(
        db.scalars(
            stmt.order_by(Fragment.verified.desc()).limit(limit),
        ).all(),
    )


def sample_fragments(
    db: Session,
    *,
    work_kind: str | None = None,
    language: str = "ru",
    tier: list[int] | None = None,
    tags: list[str] | None = None,
    include_dialogues: bool = True,
    limit: int = 10,
) -> list[Fragment]:
    """Random sample for script generation."""
    stmt = _fragment_query().where(
        Fragment.language == language,
        public_visibility_filter(),
    )

    if work_kind:
        stmt = stmt.join(Work, Fragment.work_id == Work.id).where(
            Work.kind == work_kind,
        )
    elif tier:
        stmt = stmt.join(Work, Fragment.work_id == Work.id).where(
            Work.tier.in_(tier),
        )

    if not include_dialogues:
        stmt = stmt.where(Fragment.fragment_type != "dialogue")

    if tags:
        stmt = (
            stmt.join(FragmentTag, Fragment.id == FragmentTag.fragment_id)
            .join(Tag, FragmentTag.tag_id == Tag.id)
            .where(Tag.name.in_(tags))
        )

    return list(db.scalars(stmt.order_by(func.random()).limit(limit)).all())


def get_or_create_tag(db: Session, name: str) -> Tag:
    """Return existing tag or create a new one."""
    tag = db.scalars(select(Tag).where(Tag.name == name)).first()
    if tag is None:
        tag = Tag(name=name)
        db.add(tag)
        db.flush()
    return tag
