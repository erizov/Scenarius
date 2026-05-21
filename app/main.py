from contextlib import asynccontextmanager

from pathlib import Path



import structlog

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session



from app.api.generation_router import router as generation_router
from app.api.review_router import router as review_router
from app.api.router import router as api_router

from app.config import settings

from app.db import get_db

from app.i18n import normalize_ui_lang, translate, ui_context

from app.services import fragments as fragment_service



logger = structlog.get_logger()



APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))





@asynccontextmanager

async def lifespan(app: FastAPI):

    """Application lifespan hooks."""

    logger.info("app.startup", env=settings.app_env)

    yield





app = FastAPI(

    title=settings.app_name,

    version="0.3.0",

    docs_url="/docs",

    redoc_url="/redoc",

    lifespan=lifespan,

)



static_dir = APP_DIR / "static"

static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(api_router)
app.include_router(review_router)
app.include_router(generation_router)


def _error_hint(status_code: int, lang: str) -> str | None:
    if status_code == 503:
        return translate(lang, "error_llm_hint")
    if status_code == 400:
        return translate(lang, "error_input_hint")
    return None


def _htmx_error_response(
    request: Request,
    *,
    detail: str,
    status_code: int,
) -> HTMLResponse | JSONResponse:
    if request.headers.get("HX-Request") == "true":
        lang = normalize_ui_lang(request.cookies.get("ui_lang"))
        ctx = ui_context(lang)
        return templates.TemplateResponse(
            request=request,
            name="partials/story_error.html",
            context={
                "error": detail,
                "status_code": status_code,
                "hint": _error_hint(status_code, lang),
                **ctx,
            },
            status_code=status_code,
        )
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> HTMLResponse | JSONResponse:
    """Return HTML partials for htmx error responses."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _htmx_error_response(
        request,
        detail=detail,
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> HTMLResponse | JSONResponse:
    """Surface validation errors in the comment UI."""
    detail = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    )
    return _htmx_error_response(request, detail=detail, status_code=422)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> HTMLResponse | JSONResponse:
    """Avoid silent failures; show HTML errors in the browser."""
    logger.exception("app.unhandled_error", error=str(exc))
    detail = str(exc) or "Internal server error"
    lang = normalize_ui_lang(request.cookies.get("ui_lang"))
    ctx = ui_context(lang)
    wants_html = (
        request.headers.get("HX-Request") == "true"
        or "text/html" in request.headers.get("accept", "")
    )
    if wants_html:
        return templates.TemplateResponse(
            request=request,
            name="partials/story_error.html",
            context={
                "error": detail,
                "status_code": 500,
                "hint": None,
                **ctx,
            },
            status_code=500,
        )
    return JSONResponse(status_code=500, content={"detail": detail})


def _resolve_ui_lang(request: Request, ui_lang: str | None) -> str:

    if ui_lang:

        return normalize_ui_lang(ui_lang)

    cookie = request.cookies.get("ui_lang")

    return normalize_ui_lang(cookie)





@app.get("/set-lang")

def set_lang(lang: str = Query(...), next: str = "/") -> RedirectResponse:

    """Set UI language cookie and redirect back."""

    code = normalize_ui_lang(lang)

    response = RedirectResponse(url=next, status_code=303)

    response.set_cookie("ui_lang", code, max_age=60 * 60 * 24 * 365)

    return response





@app.get("/", response_class=HTMLResponse)

def home(

    request: Request,

    q: str | None = Query(default=None),

    language: str | None = Query(default=None),

    fragment_type: str | None = Query(default=None),

    ui_lang: str | None = Query(default=None),

    db: Session = Depends(get_db),

) -> HTMLResponse:

    """Render the public quote browser."""

    lang = _resolve_ui_lang(request, ui_lang)

    rows, total = fragment_service.list_fragments(

        db,

        q=q,

        language=language,

        fragment_type=fragment_type,

        limit=20,

    )

    items = [fragment_service.fragment_to_dict(row) for row in rows]

    ctx = ui_context(lang)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "items": items,
            "total": total,
            "q": q or "",
            "language": language or "",
            "fragment_type": fragment_type or "",
            "active_nav": "browse",
            **ctx,
        },
    )


@app.get("/create", response_class=HTMLResponse)
def create_page_redirect() -> RedirectResponse:
    """Backward-compatible redirect to the comment UI."""
    return RedirectResponse(url="/comment", status_code=307)


@app.get("/comment", response_class=HTMLResponse)
def comment_page(
    request: Request,
    ui_lang: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the news comment page (RAG + LLM)."""
    lang = _resolve_ui_lang(request, ui_lang)
    ctx = ui_context(lang)
    return templates.TemplateResponse(
        request=request,
        name="comment.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "comment",
            **ctx,
        },
    )

