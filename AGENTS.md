# AGENTS.md — PM-RU Content Agent

> Agent-friendly project guide. Read this file first before making any changes.
> Updated: 2026-03-16

---

## Project Overview

**PM-RU Content Agent** is an automated pipeline for assembling marketplace product cards.

- **Redmine** is the task source and status target (control layer)
- **Figma** is the template source of truth (rendering layer)
- **AI/LLM** is an auxiliary normalization layer only — this system does NOT generate cards from scratch
- **MVP card types**: `hero`, `dimensions`, `colors`, `simple_benefit`

The system receives a Redmine issue ID, runs a 10-step Celery pipeline, fills a Figma template, exports a PNG, uploads to S3-compatible storage, and reports back to Redmine.

---

## Architecture Summary

```
FastAPI (API layer)
  └─ Celery chain (orchestration)
       ├─ Redmine client (ingest + report)
       ├─ Figma client (template fill + export)
       ├─ LLM layer (normalize + compress)
       ├─ QA engine (rule-based validation)
       └─ Storage backend (S3/Yandex)

Persistence: PostgreSQL (jobs, manifests) + Redis (Celery broker)
```

Full architecture details: `docs/architecture.md`
Phased implementation plan: `docs/phased_plan.md`
Repo structure guide: `docs/repo_structure.md`
Task folder conventions: `docs/task_management.md`

---

## Build & Run Commands

```bash
# Install dependencies (uv required)
uv sync

# Start all services (local dev)
docker-compose up

# Run database migrations
uv run alembic upgrade head

# Start API server (dev, hot reload)
uv run uvicorn content_agent.main:app --reload --port 8000

# Start Celery worker (default queue)
uv run celery -A content_agent.workers.celery_app worker -Q default -l info

# Start Celery worker (image_edit queue)
uv run celery -A content_agent.workers.celery_app worker -Q image_edit -l info

# Start Flower (monitoring)
uv run celery -A content_agent.workers.celery_app flower --port=5555

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=content_agent --cov-report=term-missing

# Run only unit tests
uv run pytest tests/unit/

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/content_agent/
```

---

## Code Style & Conventions

- **Python 3.12** — use modern typing (`list[str]` not `List[str]`, `X | Y` not `Union[X, Y]`)
- **Pydantic v2** — use `model_validator`, `field_validator`, `model_config`
- **SQLAlchemy 2.x** — use `async` sessions, `select()` style queries
- **Ruff** for linting and formatting (replaces black + isort + flake8)
- **Mypy strict** in `src/content_agent/`
- All external integrations implement an ABC from `integrations/*/base.py` — never call third-party APIs directly from Celery tasks
- All Celery tasks accept and return a `TaskManifest` dict (passed through the chain)
- Never put business logic in API routes — routes only validate input and enqueue jobs
- Prompts are versioned files in `llm/prompts/` — never hardcode prompts inline
- QA rules are declarative dataclasses in `qa/rules.py` — never hardcode checks inline

---

## Environment Variables

Copy `.env.example` to `.env` before running. Required variables:

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/content_agent
REDIS_URL=redis://localhost:6379/0
REDMINE_BASE_URL=https://redmine.example.com
REDMINE_API_KEY=...
FIGMA_ACCESS_TOKEN=...
FIGMA_TEMPLATE_REGISTRY_PATH=config/template_registry.json
STORAGE_ENDPOINT_URL=https://storage.yandexcloud.net
STORAGE_BUCKET=content-agent-exports
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
OPENAI_API_KEY=...
LLM_PROVIDER=openai          # or: mock
IMAGE_EDIT_PROVIDER=mock     # or: openai_dalle
API_KEY=...
```

---

## MVP Boundaries

**Supported card types:**
- `hero` — main product shot with title
- `dimensions` — size/dimension infographic
- `colors` — color variant grid
- `simple_benefit` — key benefit highlight

**NOT in MVP scope (do not implement):**
- `mechanisms` card type
- complex functional states
- complex interiors
- brand slides
- custom layout engine (Figma is the only rendering target)
- auto-generation of new icons
- batch processing (one Redmine issue = one card)

---

## Integration Rules

### Redmine
- Auth: `X-Redmine-API-Key` header
- On success: update issue status + add journal note with PNG URL
- On failure: add journal note with error description, do NOT change status
- Custom fields in Redmine are **in Russian** — see field name constants in `integrations/redmine/client.py` (`CF_*`)
- Full custom fields schema: `docs/task_management.md`
- Admin setup guide: `docs/redmine_setup_guide.md`
- Client: `integrations/redmine/client.py` — use only this, never raw HTTP in tasks

**Redmine custom fields (Russian name → internal key):**

| Название в Redmine | Internal key | Required |
|--------------------|--------------|---------|
| Тип карточки | `card_type` | Yes |
| URL главного изображения | `main_image_url` | Yes |
| Артикул | `product_sku` | Yes |
| Вариант | `variant` | No |
| Текст на карточке | `brief_text` | No |
| Цветовое решение | `color_scheme` | No |
| Сегмент инфографики | `segment` | No |
| Маркетплейс | `marketplace` | No |
| Номер изображения в карточке | `image_number` | No |
| Формат изображения | `image_format` | No |
| Комментарий | `comment` | No |
| Фотореференс | `photo_reference_url` | No |
| ID | `content_agent_job_id` | Auto |
| Рендер | `render_url` | Auto |

### Figma
- Templates are registered in `config/template_registry.json` (file_key + frame_id + version)
- Layer naming convention: `TEXT_*`, `IMG_MAIN`, `IMG_ICON_*`, `COLOR_SWATCH_*`
- Never modify template files — only fill instances/frames
- Export: use Figma `/images` endpoint with `format=png&scale=2`
- Figma API rate limits: implement exponential backoff (429 handling)
- Full conventions: `docs/figma_conventions.md`

### LLM
- All LLM calls go through `llm/base.py` ABC — never call OpenAI directly
- Use `MockProvider` in all tests — no real API calls in CI
- Prompts are in `llm/prompts/*.txt` — versioned, reviewable
- LLM is used ONLY for: spec normalization, text compression, icon mapping hints
- LLM is NOT used for: template selection, QA validation, Figma operations

### Storage
- Use `StorageBackend` ABC from `integrations/storage/base.py`
- Return public URL (or pre-signed URL with long TTL) for Redmine report
- Storage key format: `exports/{card_type}/{redmine_id}/{timestamp}.png`

### Image Edit (optional)
- Controlled by `manifest.meta.image_edit_enabled` flag from Redmine custom field
- Default: disabled (`MockProvider` pass-through)
- Only safe, non-destructive edits (background clean-up, color correction)

---

## Pipeline Step Reference

| Step | Task | Input | Output |
|------|------|-------|--------|
| 1 | `fetch_redmine_task` | `redmine_task_id: int` | raw Redmine issue dict |
| 2 | `build_task_manifest` | raw issue | `TaskManifest` v0 |
| 3 | `validate_manifest` | manifest v0 | manifest v1 (validated) |
| 4 | `normalize_spec` | manifest v1 | manifest v2 (LLM-normalized) |
| 5 | `compress_texts` | manifest v2 | manifest v3 (texts compressed) |
| 6 | `select_figma_template` | manifest v3 | manifest v4 (template_id set) |
| 7 | `fill_figma_template` | manifest v4 | manifest v5 (Figma updated) |
| 8 | `maybe_apply_image_edit` | manifest v5 | manifest v6 (optional) |
| 9 | `export_png` | manifest v6 | manifest v7 (png_url set) |
| 10 | `upload_to_storage` | manifest v7 | manifest v8 (storage_key set) |
| 11 | `report_to_redmine` | manifest v8 | final state |

---

## Project Skills

Skills describe the key competency modes for agents working in this repository.
When taking on a task, identify which skill(s) apply and follow the corresponding guidance.

---

### `architecture-planning`
**When:** Designing new features, evaluating trade-offs, adding integrations.
**Approach:**
- Read `docs/architecture.md` first
- Prefer abstraction (ABC) over direct coupling
- New integrations must follow the `integrations/*/base.py` ABC pattern
- New pipeline steps added to `workers/tasks/` and registered in `workers/pipeline.py`
- Document decisions in `project_tasks/<slug>/docs/`

---

### `redmine-integration`
**When:** Working with Redmine task ingest, status updates, custom fields, webhooks.
**Key files:** `integrations/redmine/`, `workers/tasks/ingest.py`, `workers/tasks/report.py`
**Rules:**
- All Redmine HTTP calls via `RedmineClient` only
- Custom field names are defined in `docs/task_management.md` — do not hardcode field IDs
- On failure: always write error to Redmine journal (never silent failure)
- Idempotent: re-triggering the same task_id must not create duplicate reports

---

### `figma-template-automation`
**When:** Working with Figma template selection, layer filling, PNG export.
**Key files:** `integrations/figma/`, `workers/tasks/template.py`, `workers/tasks/export.py`
**Rules:**
- Template registry (`config/template_registry.json`) is the single source of truth for template IDs
- Layer naming convention must match `docs/figma_conventions.md`
- Fill operations are idempotent (same manifest → same Figma state)
- Export frame IDs must be pinned in registry — never derive dynamically
- Test with mocked Figma API (never hit real API in tests)

---

### `llm-normalization`
**When:** Working with spec normalization, text compression, or any LLM-assisted processing.
**Key files:** `llm/`, `workers/tasks/normalize.py`, `workers/tasks/compress.py`
**Rules:**
- All LLM calls through `LLMProvider` ABC — never `openai.ChatCompletion` directly
- Prompts live in `llm/prompts/` as versioned `.txt` files
- Always validate LLM output with Pydantic schema — never trust raw LLM text
- Fallback strategy: if LLM fails, pass-through original text with warning in manifest
- Use `MockProvider` in all unit and integration tests

---

### `image-edit-routing`
**When:** Working with the optional image edit step.
**Key files:** `integrations/image_edit/`, `workers/tasks/image_edit.py`
**Rules:**
- Step is controlled by `manifest.meta.image_edit_enabled` — always check this flag
- Default provider is `MockProvider` (pass-through) — never enable real provider without explicit config
- Image edit tasks run in dedicated Celery queue `image_edit` (rate-limit isolation)
- Only safe edits: background removal, color correction — no creative generation
- Log provider name and latency in manifest breadcrumbs

---

### `qa-rules`
**When:** Adding or modifying validation rules, checking manifest correctness.
**Key files:** `qa/rules.py`, `qa/validator.py`, `workers/tasks/validate.py`
**Rules:**
- Rules are declarative `Rule` dataclasses — never inline `if/else` checks in tasks
- Each rule targets specific `card_types` or `"all"`
- `ValidationResult` contains list of errors (blocking) and warnings (non-blocking)
- Blocking errors stop the pipeline and report to Redmine
- Non-blocking warnings are stored in `manifest.meta.errors` and continue
- Adding a new card type requires adding corresponding rules

---

### `storage-export`
**When:** Working with PNG upload, storage backends, URL generation.
**Key files:** `integrations/storage/`, `workers/tasks/export.py`, `workers/tasks/storage.py`
**Rules:**
- Use `StorageBackend` ABC — never call boto3 directly from tasks
- Storage key format: `exports/{card_type}/{redmine_id}/{timestamp}.png`
- Always return URL (public or pre-signed with long TTL)
- `S3Backend` supports Yandex Object Storage via `endpoint_url` config
- Test with `MockStorageBackend` that stores files in-memory

---

### `task-orchestration`
**When:** Working with Celery pipeline, job state, error handling, retries.
**Key files:** `workers/pipeline.py`, `workers/celery_app.py`, `workers/tasks/`
**Rules:**
- All tasks accept `TaskManifest` dict, return updated `TaskManifest` dict
- Each task updates `manifest.meta.pipeline_step` on entry
- Failed tasks: `max_retries=3`, `default_retry_delay=30s`, exponential backoff
- On unrecoverable failure: call `report_to_redmine` with error details
- Job state machine: `PENDING → RUNNING → {step_name} → SUCCESS | FAILED`
- Never access DB directly from tasks — use `manifest` dict as state carrier

---

### `task-folder-management`
**When:** Creating or resuming work on a Redmine task in this repository.
**Key files:** `project_tasks/`, `docs/task_management.md`
**Rules:**
- Create task folder immediately when starting work: `project_tasks/<task_slug>/`
- Slug format: `redmine-{id}-{card_type}-{product_slug}` (e.g., `redmine-1042-hero-sneaker-x`)
- Full folder structure must be created at once (see `docs/task_management.md`)
- Always update `status.md` when switching between tasks or resuming
- Breadcrumbs are append-only — never delete breadcrumb entries
- All decisions and edge cases go in `docs/notes.md` within the task folder

---

### `docs-and-breadcrumbs`
**When:** Documenting decisions, recording pipeline execution history, writing notes.
**Key files:** `project_tasks/<slug>/breadcrumbs/`, `project_tasks/<slug>/docs/`
**Rules:**
- Breadcrumb filename format: `{ISO_DATETIME}_{step_name}.md` (e.g., `2026-03-16T10-00_ingest.md`)
- Each breadcrumb records: step name, input summary, output summary, duration, errors
- `docs/notes.md` is for human-readable context: edge cases, designer feedback, manual overrides
- `plan.md` in task folder is a living checklist — update as steps complete
- Never leave a task folder with empty `status.md`

---

## Working With Task Folders

When picking up a task:
1. Check `project_tasks/` for existing folder matching the Redmine issue ID
2. Read `status.md` to understand current state
3. Read `breadcrumbs/` (latest file) to see last action
4. Read `plan.md` for remaining work
5. If no folder exists, create it following `docs/task_management.md`

```bash
# Scaffold a new task folder (replace values)
TASK_SLUG="redmine-1042-hero-sneaker-x"
mkdir -p project_tasks/$TASK_SLUG/{tasks,jobs,breadcrumbs,docs}
touch project_tasks/$TASK_SLUG/status.md
touch project_tasks/$TASK_SLUG/plan.md
```

---

## Common Pitfalls

- **Do not** call `openai` / `boto3` / `httpx` directly in Celery task files — always use integration layer
- **Do not** add business logic to FastAPI routes — routes only validate and enqueue
- **Do not** commit `.env` — only `.env.example`
- **Do not** modify Figma template files — only fill frames
- **Do not** implement batch processing in MVP — one Redmine issue = one card
- **Do not** implement unsupported card types (mechanisms, brand slides, etc.) in MVP
- **Do not** hardcode Figma frame IDs — use `template_registry.json`
- **Do not** run real API calls in tests — use mock providers

---

## Key Files Quick Reference

| Purpose | File |
|---------|------|
| All config / env vars | `src/content_agent/config.py` |
| Pipeline chain builder | `src/content_agent/workers/pipeline.py` |
| TaskManifest schema | `src/content_agent/schemas/task_manifest.py` |
| QA rules | `src/content_agent/qa/rules.py` |
| Figma template registry | `config/template_registry.json` |
| LLM prompts | `src/content_agent/llm/prompts/` |
| Architecture doc | `docs/architecture.md` |
| Phased plan | `docs/phased_plan.md` |
| Task folder conventions | `docs/task_management.md` |
