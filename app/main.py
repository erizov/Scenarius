from contextlib import asynccontextmanager

from pathlib import Path



import structlog

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session



from app.api.generation_router import router as generation_router
from app.api.review_router import router as review_router
from app.api.router import router as api_router

from app.config import settings

from app.db import get_db

from app.i18n import normalize_ui_lang, ui_context

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


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> HTMLResponse | JSONResponse:
    """Return HTML partials for htmx error responses."""
    if request.headers.get("HX-Request") == "true":
        lang = normalize_ui_lang(request.cookies.get("ui_lang"))
        ctx = ui_context(lang)
        return templates.TemplateResponse(
            request=request,
            name="partials/story_error.html",
            context={"error": exc.detail, **ctx},
            status_code=exc.status_code,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


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
def create_page(
    request: Request,
    ui_lang: str | None = Query(default=None),
) -> HTMLResponse:
    """Render the story generation page."""
    lang = _resolve_ui_lang(request, ui_lang)
    ctx = ui_context(lang)
    return templates.TemplateResponse(
        request=request,
        name="create.html",
        context={
            "app_name": settings.app_name,
            "active_nav": "create",
            **ctx,
        },
    )

