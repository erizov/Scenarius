import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PersonBrief(BaseModel):
    """Minimal person representation."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    role: str | None = None


class WorkBrief(BaseModel):
    """Minimal work representation."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    kind: str
    year: int | None = None
    tier: int
    language: str


class SourceRefOut(BaseModel):
    """Provenance record for API responses."""

    model_config = ConfigDict(from_attributes=True)

    source_site: str
    source_url: str | None = None
    license_hint: str | None = None
    scraped_at: datetime | None = None


class FragmentOut(BaseModel):
    """Fragment returned by the public API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    fragment_type: str
    language: str
    verified: bool
    review_status: str | None = None
    context: str | None = None
    work: WorkBrief | None = None
    speaker: PersonBrief | None = None
    tags: list[str] = Field(default_factory=list)
    sources: list[SourceRefOut] = Field(default_factory=list)


class FragmentListOut(BaseModel):
    """Paginated fragment list."""

    items: list[FragmentOut]
    total: int
    limit: int
    offset: int


class FragmentMatchRequest(BaseModel):
    """Request body for semantic/keyword fragment matching."""

    context: str = Field(min_length=3, max_length=2000)
    language: str = "ru"
    tier: list[int] | None = None
    limit: int = Field(default=5, ge=1, le=50)
    mode: str = Field(default="keyword", pattern="^(keyword|semantic)$")


class FragmentSampleRequest(BaseModel):
    """Request body for sampling fragments for script generation."""

    work_kind: str | None = None
    language: str = "ru"
    tier: list[int] | None = None
    tags: list[str] = Field(default_factory=list)
    include_dialogues: bool = True
    limit: int = Field(default=10, ge=1, le=100)


class ReviewListOut(BaseModel):
    """Paginated review queue."""

    items: list[FragmentOut]
    total: int
    limit: int
    offset: int
    pending: int
    approved: int
    rejected: int


class ReviewActionOut(BaseModel):
    """Result of approve/reject action."""

    id: uuid.UUID
    review_status: str
    verified: bool


class StoryCitationOut(BaseModel):
    """Corpus fragment cited during generation."""

    id: uuid.UUID
    text: str
    fragment_type: str
    work_title: str | None = None


class StoryGenerateRequest(BaseModel):
    """Request body for news-based story generation."""

    url: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=4000)
    format: str = Field(
        default="comment",
        pattern="^(comment|parable|fairy_tale|anecdote|story)$",
    )
    language: str = Field(default="ru", pattern="^(ru|en)$")


class StoryGenerateOut(BaseModel):
    """Generated story response."""

    story: str
    format: str
    language: str
    news_title: str
    news_source_url: str | None = None
    citations: list[StoryCitationOut] = Field(default_factory=list)
    provider: str
    model: str
