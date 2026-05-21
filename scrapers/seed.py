"""Seed demo data and sync canonical works into the database."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    FragmentType,
    Person,
    PersonRole,
    Work,
    WorkKind,
    WorkPerson,
)
from scrapers.canonical import load_authors, load_fragments, load_works
from scrapers.ingest import upsert_fragment


def sync_works(db: Session) -> dict[str, Work]:
    """Upsert canonical works and return slug -> Work map."""
    by_slug: dict[str, Work] = {}
    for item in load_works():
        slug = item["id"]
        work = db.scalars(select(Work).where(Work.slug == slug)).first()
        if work is None:
            work = Work(
                slug=slug,
                title=item["title"],
                kind=WorkKind(item["kind"]),
                tier=item.get("tier", 1),
                language=item["language"],
                year=item.get("year"),
                meta={"tags": item.get("tags", [])},
            )
            db.add(work)
            db.flush()
        else:
            work.title = item["title"]
            work.tier = item.get("tier", work.tier)
            work.meta = {"tags": item.get("tags", [])}
        by_slug[slug] = work
    return by_slug


def sync_authors(db: Session) -> dict[str, Person]:
    """Upsert canonical authors and return slug -> Person map."""
    by_slug: dict[str, Person] = {}
    for item in load_authors():
        slug = item["id"]
        person = db.scalars(select(Person).where(Person.slug == slug)).first()
        if person is None:
            person = Person(
                slug=slug,
                name=item["name"],
                meta={"roles": item.get("roles", [])},
            )
            db.add(person)
            db.flush()
        else:
            person.name = item["name"]
        by_slug[slug] = person
    return by_slug


def link_work_people(db: Session, works: dict[str, Work]) -> None:
    """Link authors/directors from works.yaml to works."""
    authors = sync_authors(db)
    for item in load_works():
        work = works[item["id"]]
        for author_id in item.get("authors", []):
            person = authors.get(author_id)
            if person is None:
                continue
            role = PersonRole.director
            if author_id in {"pushkin", "bulgakov", "dostoevsky", "exupery"}:
                role = PersonRole.author
            exists = db.scalars(
                select(WorkPerson).where(
                    WorkPerson.work_id == work.id,
                    WorkPerson.person_id == person.id,
                    WorkPerson.role == role,
                ),
            ).first()
            if exists is None:
                db.add(
                    WorkPerson(
                        work_id=work.id,
                        person_id=person.id,
                        role=role,
                    ),
                )


def sync_fragments(db: Session, works: dict[str, Work]) -> int:
    """Upsert curated famous fragments from fragments.yaml."""
    authors = sync_authors(db)
    created = 0
    for item in load_fragments():
        work = works.get(item["work_id"])
        speaker = authors.get(item["speaker"]) if item.get("speaker") else None
        fragment, is_new = upsert_fragment(
            db,
            text=item["text"],
            language=item["language"],
            fragment_type=FragmentType(item["fragment_type"]),
            source_site="canonical",
            license_hint="curated",
            work=work,
            speaker_name=speaker.name if speaker else None,
            tags=item.get("tags", []),
            verified=item.get("verified", True),
            embed=False,
        )
        if is_new:
            created += 1
        elif item.get("verified", True) and not fragment.verified:
            fragment.verified = True
        meta = dict(fragment.meta or {})
        meta["review_status"] = "approved"
        fragment.meta = meta
    return created


def run_seed(db: Session) -> None:
    """Sync canonical registry and curated fragments."""
    works = sync_works(db)
    sync_authors(db)
    link_work_people(db, works)
    created = sync_fragments(db, works)
    db.commit()
    print(f"Canonical sync complete. New fragments: {created}")
