# Phased Implementation Plan — PM-RU Content Agent

## Overview

7 phases, sequenced to deliver working value at each milestone.
Each phase ends with a verifiable checkpoint.

---

## Phase 1 — Foundation & Skeleton

**Goal:** Runnable project with Docker Compose, FastAPI health check, DB migrations, Celery worker ping.

### Tasks
- [ ] Initialize `pyproject.toml` (uv, Python 3.12)
- [ ] Set up `docker-compose.yml` (api, worker, postgres, redis, flower)
- [ ] `src/content_agent/config.py` — pydantic-settings with all env vars
- [ ] `src/content_agent/main.py` — FastAPI app factory, `GET /health`
- [ ] `src/content_agent/db/` — SQLAlchemy async session, Base model
- [ ] `alembic/` init + first migration (jobs table, task_manifests table)
- [ ] `src/content_agent/workers/celery_app.py` — Celery app with Redis broker
- [ ] `.env.example` — all required environment variables documented
- [ ] `README.md` — quick start instructions

### Deliverable
```bash
docker-compose up
curl http://localhost:8000/health  # → {"status": "ok"}
celery -A content_agent.workers.celery_app inspect ping  # worker responds
```

### Dependencies
- Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Celery, Redis, Postgres

---

## Phase 2 — Redmine Integration & Task Manifest

**Goal:** System can fetch a Redmine issue and produce a validated `TaskManifest`.

### Tasks
- [ ] `integrations/redmine/client.py` — REST client, `get_issue(id)`, `update_issue(id, ...)`
- [ ] `integrations/redmine/schemas.py` — Pydantic models for Redmine issue/custom fields
- [ ] `schemas/task_manifest.py` — full `TaskManifest` Pydantic v2 model
- [ ] `workers/tasks/ingest.py` — `fetch_redmine_task` Celery task
- [ ] `workers/tasks/manifest.py` — `build_task_manifest` Celery task
- [ ] `api/routes/tasks.py` — `POST /tasks/trigger`
- [ ] `api/routes/jobs.py` — `GET /jobs/{job_id}`
- [ ] DB: persist job record on trigger, update on each step
- [ ] Unit tests: manifest builder, Redmine schema parsing

### Deliverable
```bash
curl -X POST http://localhost:8000/tasks/trigger \
  -d '{"redmine_task_id": 1042}'
# Returns: {"job_id": "abc-123"}
curl http://localhost:8000/jobs/abc-123
# Returns: {"step": "build_task_manifest", "state": "SUCCESS", "manifest": {...}}
```

### Redmine Custom Fields Contract
Team must agree on custom field names before this phase starts.
Required fields:
- `card_type` (hero/dimensions/colors/simple_benefit)
- `main_image_url`
- `product_sku`
- `image_edit_enabled` (boolean)

---

## Phase 3 — QA Rules & LLM Normalization

**Goal:** Manifest is validated by rules engine and enriched by LLM normalization + text compression.

### Tasks
- [ ] `qa/rules.py` — declarative rule definitions per card type
- [ ] `qa/validator.py` — rule runner, returns `ValidationResult` with error list
- [ ] `workers/tasks/validate.py` — `validate_manifest` Celery task
- [ ] `llm/base.py` — `LLMProvider` ABC (`complete(prompt, input) → str`)
- [ ] `llm/providers/mock.py` — deterministic mock for tests
- [ ] `llm/providers/openai.py` — OpenAI async client
- [ ] `llm/prompts/` — versioned prompt files (normalize.txt, compress.txt)
- [ ] `llm/normalizer.py` — `normalize_spec(raw_text) → structured dict`
- [ ] `llm/compressor.py` — `compress_text(text, max_chars) → str`
- [ ] `workers/tasks/normalize.py` — `normalize_spec` Celery task
- [ ] `workers/tasks/compress.py` — `compress_texts` Celery task
- [ ] Unit tests: all QA rules, normalizer with mock LLM, compressor

### QA Rules (MVP)

| Rule | Card Types | Description |
|------|-----------|-------------|
| `required_fields` | all | title, card_type, main_image_url must be present |
| `title_length` | all | title ≤ 60 chars |
| `description_length` | hero, simple_benefit | description ≤ 200 chars |
| `benefit_length` | simple_benefit | each benefit ≤ 80 chars |
| `image_url_format` | all | main_image_url must be valid HTTPS URL |
| `color_count` | colors | 2–8 swatches required |
| `dimension_count` | dimensions | 3–6 entries required |

### Deliverable
Manifest with normalized text passes all QA rules. LLM mock used in tests.

---

## Phase 4 — Figma Integration

**Goal:** System selects the correct Figma template and fills all text/asset layers automatically.

### Tasks
- [ ] `integrations/figma/client.py` — REST client (get file, update nodes, export image)
- [ ] `integrations/figma/template_registry.py` — maps card_type → (file_key, frame_id, version)
- [ ] `integrations/figma/filler.py` — `fill_template(manifest) → fill_map`
- [ ] `workers/tasks/template.py` — `select_figma_template` + `fill_figma_template` Celery tasks
- [ ] Config: `FIGMA_ACCESS_TOKEN`, `FIGMA_TEMPLATE_REGISTRY_PATH`
- [ ] Unit tests: filler mapping, template selection logic
- [ ] Integration test: mock Figma API responses

### Fill Strategy
1. Text layers identified by their Figma layer name (convention: `TEXT_TITLE`, `TEXT_DESCRIPTION`, `TEXT_BENEFIT_1`, etc.)
2. Image substitution: replace fill in image layers via Figma plugin API or manual process flag
3. `fill_map` stored in manifest for audit trail

### Figma Layer Naming Convention
All templates must follow naming convention (documented in `docs/figma_conventions.md`):
- `TEXT_*` — text layers (auto-filled)
- `IMG_MAIN` — main product image layer
- `IMG_ICON_*` — icon layers
- `COLOR_SWATCH_*` — color swatch layers

### Deliverable
For a given manifest, Figma frame is updated with correct text content.

---

## Phase 5 — Export & Storage

**Goal:** Filled Figma frame is exported as PNG and uploaded to S3-compatible storage.

### Tasks
- [ ] `workers/tasks/export.py` — `export_png` Celery task (Figma `/images` endpoint)
- [ ] `integrations/storage/base.py` — `StorageBackend` ABC
- [ ] `integrations/storage/s3.py` — boto3 implementation with Yandex endpoint support
- [ ] `workers/tasks/storage.py` — `upload_to_storage` Celery task
- [ ] Config: `STORAGE_ENDPOINT_URL`, `STORAGE_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- [ ] Unit tests: storage backend mock, export task

### Deliverable
PNG file available at public/pre-signed URL in object storage.

---

## Phase 6 — Pipeline Assembly & Redmine Reporting

**Goal:** Full end-to-end pipeline runs as single Celery chain. Redmine issue updated on completion.

### Tasks
- [ ] `workers/pipeline.py` — build full chain, handle `chord` for parallel steps if needed
- [ ] `workers/tasks/report.py` — `report_to_redmine` (update status, add journal note with URL)
- [ ] `integrations/image_edit/base.py` — `ImageEditProvider` ABC
- [ ] `integrations/image_edit/providers/mock.py` — pass-through mock
- [ ] `workers/tasks/image_edit.py` — `maybe_apply_image_edit` (skip if disabled)
- [ ] Job state machine: PENDING → RUNNING → step_name → SUCCESS / FAILED
- [ ] Error handling: failed step writes error to Redmine journal, sets job FAILED
- [ ] `api/routes/webhooks.py` — Redmine webhook endpoint
- [ ] Integration test: full pipeline with all mocks

### Error Handling Strategy
- Each Celery task: `max_retries=3`, `default_retry_delay=30s`
- On final failure: `report_to_redmine` called with error details
- Manifest `meta.errors` accumulates non-fatal warnings

### Deliverable
```
POST /tasks/trigger {"redmine_task_id": 1042}
→ Full pipeline runs
→ Redmine issue #1042 updated: status=Done, journal note with PNG URL
```

---

## Phase 7 — Observability, Hardening & Docs

**Goal:** Production-ready MVP with monitoring, structured logging, complete docs.

### Tasks
- [ ] Structured logging with `structlog` (JSON output, per-request correlation ID)
- [ ] Celery task events → Flower (configure `CELERY_SEND_EVENTS=true`)
- [ ] Prometheus metrics endpoint (`/metrics`) — job count, pipeline duration, error rate
- [ ] Retry policies review and hardening
- [ ] Security: API key auth on FastAPI routes (`X-API-Key` header)
- [ ] Rate limiting: Figma API calls (429 handling with exponential backoff)
- [ ] `docs/runbook.md` — operational procedures
- [ ] `docs/figma_conventions.md` — template layer naming standards
- [ ] Final AGENTS.md review
- [ ] Performance test: 10 concurrent pipeline jobs

### Deliverable
Demo-ready MVP. Monitoring visible in Flower. Logs structured and searchable.

---

## Summary Timeline

| Phase | Focus | Est. Effort |
|-------|-------|-------------|
| 1 | Foundation | 1–2 days |
| 2 | Redmine + Manifest | 2–3 days |
| 3 | QA + LLM | 2–3 days |
| 4 | Figma | 3–4 days |
| 5 | Export + Storage | 1–2 days |
| 6 | Pipeline + Report | 2–3 days |
| 7 | Observability | 1–2 days |
| **Total** | | **12–19 days** |

---

## Key Dependencies & Blockers

| Blocker | Phase Affected | Owner |
|---------|---------------|-------|
| Redmine custom fields schema agreed | Phase 2 | Team |
| Figma templates created with correct layer naming | Phase 4 | Designer |
| Figma access token with write permissions | Phase 4 | DevOps |
| S3/Yandex bucket created + credentials | Phase 5 | DevOps |
| OpenAI API key | Phase 3 | Team |
| Redmine API key | Phase 2 | Team |
