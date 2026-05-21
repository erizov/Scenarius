"""Story generation API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.i18n import normalize_ui_lang, translate, ui_context
from app.schemas import StoryCitationOut, StoryGenerateOut
from app.services.generation import generate_story
from app.services.llm import LLMUnavailableError
from app.services.news import NewsInputError

router = APIRouter(prefix="/api/v1", tags=["stories"])

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

FORMAT_KEYS = {
    "comment": "format_comment",
    "parable": "format_parable",
    "fairy_tale": "format_fairy_tale",
    "anecdote": "format_anecdote",
    "story": "format_story",
}


def _format_label(language: str, story_format: str) -> str:
    key = FORMAT_KEYS.get(story_format, "format_comment")
    return translate(language, key)


def _parse_request_data(raw: dict[str, Any]) -> dict[str, Any]:
    url = raw.get("url")
    text = raw.get("text")
    return {
        "url": url.strip() if isinstance(url, str) and url.strip() else None,
        "text": text.strip() if isinstance(text, str) and text.strip() else None,
        "format": raw.get("format", "comment"),
        "language": raw.get("language", "ru"),
    }


def _story_to_schema(result) -> StoryGenerateOut:
    return StoryGenerateOut(
        story=result.story,
        format=result.format,
        language=result.language,
        news_title=result.news_title,
        news_source_url=result.news_source_url,
        citations=[
            StoryCitationOut(
                id=item.id,
                text=item.text,
                fragment_type=item.fragment_type,
                work_title=item.work_title,
            )
            for item in result.citations
        ],
        provider=result.provider,
        model=result.model,
    )


@router.post("/stories/generate")
async def generate_story_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate a short story from news using corpus RAG."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        raw = await request.json()
    else:
        form = await request.form()
        raw = dict(form)

    from app.schemas import StoryGenerateRequest

    body = StoryGenerateRequest.model_validate(_parse_request_data(raw))

    try:
        result = generate_story(
            db,
            url=body.url,
            text=body.text,
            story_format=body.format,
            language=body.language,
        )
    except NewsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = _story_to_schema(result)
    if request.headers.get("HX-Request") == "true":
        ctx = ui_context(body.language)
        return templates.TemplateResponse(
            request=request,
            name="partials/story_result.html",
            context={
                "result": payload.model_dump(),
                "format_label": _format_label(body.language, body.format),
                **ctx,
            },
        )
    return payload
