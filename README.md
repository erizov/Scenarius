# Scenarius

Soviet and post-Soviet quote corpus for news commentary and script
generation. Stores quotes, dialogues, aphorisms, proverbs, and fairy-tale
formulas **as-is** (no translation), with full source provenance and
deduplication.

## Stack and version

**Project root:** `E:\Python\GptEngineer\Scenarius`

| Component | Version / location |
|-----------|-------------------|
| **Scenarius** | 0.3.0 |
| **Python** | ≥ 3.11 (Docker image: 3.12) |
| **PostgreSQL (active)** | **18.3** — `localhost:5434` (`POSTGRES_TARGET=pg16` in `.env`) |
| **Database** | `scenarius@localhost:5434/scenarius` |
| **pgvector** | not installed on active instance — semantic RAG needs pgvector (use Docker on **5435** or run `setup_db_extensions.sql`) |
| **Embeddings** | `paraphrase-multilingual-MiniLM-L12-v2`, 384 dims (when pgvector present) |
| **Docker DB (alt.)** | PostgreSQL **16** + pgvector — `localhost:5435` (`POSTGRES_TARGET=docker`) |
| **Instance map** | [`data/postgres_instances.yaml`](data/postgres_instances.yaml) |
| **Migrations** | `alembic/versions/` (`001` schema, `002` pgvector) |
| **Ingest pull log** | `data/ingest_pull_log.json` |

### Current corpus (live DB)

Last updated from `python -m scrapers.cli stats` on **2026-05-21**:

| Metric | Count |
|--------|------:|
| **Fragments** | **9,598** / 100,000 target |
| RU | 7,169 |
| EN | 2,428 |
| Verified | 77 |
| Review queue (pending) | 5,558 |
| Works | 3,100 |

**By source:** citaty.info 3,185 · culture.ru 2,695 · wikiquote.en 2,412 · wikiquote.ru 1,226 · canonical 77 · anekdot.ru 5

Refresh: `python -m scrapers.cli stats`

## Quick start

### Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
docker compose exec app python -m scrapers.cli seed
docker compose exec app python -m scrapers.cli ingest-all
```

Open http://localhost:8008 — comment on news at `/comment`, browse corpus at `/`.

API docs: http://localhost:8008/docs

UI language toggle: **RU / EN** (top-right, persisted in cookie).

### Local development

Requirements: Python 3.11+, PostgreSQL 16 with pgvector.

```bash
cd E:\Python\GptEngineer\Scenarius
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Use the **Scenarius** venv (not another project's venv like Aphorium).

```bash
cp .env.example .env
```
docker compose up db -d

alembic upgrade head
python -m scrapers.cli seed
python -m scrapers.cli ingest-all
.\scripts\start_ui.ps1
```

## Ingest pipeline (priority order)

```bash
python -m scrapers.cli seed          # verified must-haves (movies, songs, poems)
python -m scrapers.cli ingest-all    # toward 100k target (see data/corpus.yaml)
python -m scrapers.cli stats --watch
```

`ingest-all` writes a pull log to `data/ingest_pull_log.json`. Successful URLs
are skipped on the next run; failed URLs are retried. Use `--no-pull-log` to
refetch everything, or `--pull-log-path` for a custom log file.

By default the pipeline **fails fast** — the first HTTP or config error stops
`ingest-all`. Use `--no-fail-fast` to log errors and continue with remaining
sources/pages.

**Corpus target:** 100,000 fragments (`data/corpus.yaml`). Scraped items land in
the review queue (`GET /api/v1/review/queue`); approve before using in scripts.

- **RU** = tier 1 (primary search)
- **EN** = tier 2 (foreign classics)
- **Canonical seed** = verified, no review needed
- **Scraped** = `review_status: pending` until approved

Review API:

```http
GET  /api/v1/review/queue
POST /api/v1/review/{id}/approve
POST /api/v1/review/{id}/reject
```

Sources (in order): **citaty.info** → **culture.ru** → **anekdot.ru** →
**ru.wikisource.org** (fairy tales) → **ru.wiktionary.org** (proverbs) →
**ru.wikiquote.org** → **en.wikiquote.org** → **en.wikisource.org** →
**poetrydb.org** → **gutenberg.org** → optional: **quotable.io**,
**opensubtitles.com** (API key), **ruscorpora.ru** (API key), **pushdom.ru**
(configured dataset URLs). Toggle sources via `enabled:` in
[`data/sources.yaml`](data/sources.yaml).

Individual commands also support `--no-pull-log`, `--pull-log-path`, and
`--no-fail-fast`.

Monitor running totals while ingest is in progress (updates every ~10 quotes
once batch commits land):

```powershell
python -m scrapers.cli stats --watch
# or
.\scripts\ingest_stats.ps1 -Watch
```

`ingest-all` is slow by design (~1 s between HTTP requests). Expect several
minutes per step; watch the ingest terminal for `citaty.progress` lines.

Duplicates are merged by `text_fingerprint` (SHA-256 of normalized text +
language). New sources attach as `SourceRef` on existing fragments.

## API (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/fragments` | List/search fragments |
| GET | `/api/v1/fragments/{id}` | Single fragment |
| POST | `/api/v1/fragments/match` | Match (`mode`: `keyword` or `semantic`) |
| POST | `/api/v1/fragments/sample` | Random sample for scripts |
| POST | `/api/v1/stories/generate` | Generate story from news (RAG + LLM) |
| GET | `/api/v1/health` | Health check |

Semantic search uses **pgvector** + `fastembed`
(`paraphrase-multilingual-MiniLM-L12-v2`, 384 dims).

## News commentary (RAG + LLM)

Comment on news via **link or pasted text**. The app retrieves relevant corpus
fragments (semantic match + style sampling), then generates an ironic cultural
commentary. Optional formats: parable, fairy tale, anecdote, story.

**UI scripts (Windows):**

```powershell
.\scripts\start_ui.ps1      # http://127.0.0.1:8008/comment
.\scripts\stop_ui.ps1
.\scripts\restart_ui.ps1
```

Set `APP_HOST` / `APP_PORT` in `.env`. Logs: `.run/ui.log`.

**UI:** http://localhost:8008/comment (legacy `/create` redirects here)

**API:**

```http
POST /api/v1/stories/generate
Content-Type: application/json

{
  "text": "News text...",
  "format": "comment",
  "language": "ru"
}
```

Use `"url": "https://..."` instead of `"text"` to fetch an article.

**LLM setup** (local first, cloud fallback):

```powershell
ollama pull llama3.2
ollama serve
```

Optional fallback in `.env`:

```env
LLM_PROVIDER=auto
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Install OpenAI client if needed: `pip install scenarius[llm]`.

Generation uses corpus RAG (`match` + style sampling) then Ollama; if Ollama is
unavailable and `OPENAI_API_KEY` is set, falls back to `gpt-4o-mini`. Quality
improves with a larger corpus — run `ingest-all` first.

## Project layout

Root: `E:\Python\GptEngineer\Scenarius`

```
app/              FastAPI, models, pgvector, UI i18n, /comment
scrapers/         citaty.info, Wikiquote, dedup, ingest
data/canonical/   works.yaml, authors.yaml, must-haves
data/sources.yaml ingest source registry
data/corpus.yaml  100k target and per-source budgets
alembic/          migrations (incl. pgvector)
tests/
```

## Tests

```bash
pytest -q
```

## Troubleshooting

### Multiple PostgreSQL versions (Windows)

This machine may have several Postgres installs. Scenarius uses **`.env`**
`POSTGRES_TARGET` (not port 5432 by default):

| Target | Port | pgvector |
|--------|------|----------|
| `docker` | 5435 | yes (recommended) |
| `pg18` | 5434 | install via `scripts/install_pgvector.ps1` |
| `pg16` | 5434 | install separately |
| `pg17` | 5433 | install separately |
| `pg15` | 5432 | no |

```powershell
.\scripts\detect_postgres.ps1          # show ports + current .env target
.\scripts\setup_db.ps1                 # create user/db on chosen instance
.\scripts\migrate_fresh.ps1            # reset + alembic upgrade head
```

Set target in `.env`:

```env
POSTGRES_TARGET=pg18
POSTGRES_PORT=5434
```

### pgvector on native PostgreSQL 18 (Windows)

Migration `002` may skip `fragment_embeddings` if pgvector was missing at first
run. After installing the extension:

```powershell
# Run PowerShell as Administrator
.\scripts\install_pgvector.ps1 -PgMajor 18
# As postgres superuser:
psql -U postgres -h localhost -p 5434 -d scenarius -f scripts\setup_db_extensions.sql
alembic upgrade head
python -m scrapers.cli embed-all
```

Or use Docker (pgvector included):

```powershell
docker compose up db -d
# POSTGRES_TARGET=docker  POSTGRES_PORT=5435
alembic upgrade head
```

Migration `002` skips `fragment_embeddings` when pgvector is not available on
the server; keyword search still works. Semantic search needs pgvector (Docker
or `setup_db_extensions.sql` on a server with the extension installed).

### `password authentication failed for user "scenarius"`

The app is pointing at a different Postgres instance than where you ran
`setup_db.ps1`. Check `POSTGRES_PORT` / run `detect_postgres.ps1`, then:

```powershell
.\scripts\setup_db.ps1
alembic upgrade head
```

Or override fully:

```env
DATABASE_URL=postgresql+psycopg://YOUR_USER:YOUR_PASS@localhost:5434/YOUR_DB
```

The database Scenarius uses (from .env: POSTGRES_TARGET=pg16, port 5434) is PostgreSQL 18.3, not 16.

Path	                                Purpose
C:\Program Files\PostgreSQL\18\         install root
C:\Program Files\PostgreSQL\18\bin\     binaries (psql, pg_ctl, …)
C:\Program Files\PostgreSQL\18\data\    data directory (postgresql.conf has port = 5434)

Windows service: postgresql-x64-18 (Running).
postgresql-x64-16 is Stopped — its config also had port 5434, but what's listening now is PG 18.

Note for RAG: pgvector is not installed on this instance, so semantic search isn't active yet; the app falls back to keyword matching. For full RAG you'd need pgvector on PG 18 or switch to Docker on port 5435 (POSTGRES_TARGET=docker).
