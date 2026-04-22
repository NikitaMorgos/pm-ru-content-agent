# Architecture — PM-RU Content Agent

## Overview

Automated pipeline for assembling marketplace product cards.
- **Redmine** — task source and feedback target (control layer)
- **Figma** — template source of truth (rendering layer)
- **AI** — auxiliary normalization layer only (not a generative system)
- **Scope**: hero, dimensions, colors, simple_benefit card types

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                        │
│   POST /tasks/trigger   GET /jobs/{id}   POST /webhooks/redmine  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ enqueue job
┌──────────────────────────────▼──────────────────────────────────┐
│                   Orchestration Layer (Celery)                    │
│                                                                   │
│  fetch_redmine_task                                               │
│       → build_task_manifest                                       │
│           → validate_manifest          ← QA Rules Engine         │
│               → normalize_spec         ← LLM Layer               │
│                   → compress_texts     ← LLM Layer               │
│                       → select_figma_template                     │
│                           → fill_figma_template                   │
│                               → maybe_apply_image_edit (opt.)    │
│                                   → export_png                    │
│                                       → upload_to_storage         │
│                                           → report_to_redmine     │
└──────┬───────────┬──────────────┬───────────────┬───────────────┘
       │           │              │               │
┌──────▼──┐  ┌─────▼────┐  ┌─────▼───┐  ┌────────▼──────┐
│ Redmine │  │  Figma   │  │   LLM   │  │   Storage     │
│ Client  │  │  Client  │  │  Layer  │  │  Abstraction  │
│ (REST)  │  │  (REST)  │  │  (ABC)  │  │  (S3/Yandex)  │
└─────────┘  └──────────┘  └─────────┘  └───────────────┘
       │           │              │               │
┌──────▼───────────▼──────────────▼───────────────▼───────────────┐
│                    Persistence Layer                              │
│   PostgreSQL (jobs, manifests, audit log)  │  Redis (broker)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### API Layer (`src/content_agent/api/`)

FastAPI application exposing:
- `POST /tasks/trigger` — accepts `{redmine_task_id}`, enqueues Celery chain, returns `job_id`
- `GET /jobs/{job_id}` — returns current job state, step, and result URL
- `POST /webhooks/redmine` — receives Redmine webhook events (issue updated/created)
- `GET /health` — liveness check

### Orchestration Layer (`src/content_agent/workers/`)

**Celery** with Redis as broker and Postgres as result backend (via SQLAlchemy).

Chosen over RQ because:
1. Native `chain()` / `chord()` support for sequential pipeline with per-step retry
2. Task routing — `image_edit` tasks routed to dedicated queue for rate-limit isolation
3. Flower for pipeline monitoring without custom UI
4. Per-task `max_retries`, `countdown`, `acks_late` configuration

Pipeline chain:
```python
chain(
    fetch_redmine_task.s(task_id),
    build_task_manifest.s(),
    validate_manifest.s(),
    normalize_spec.s(),
    compress_texts.s(),
    select_figma_template.s(),
    fill_figma_template.s(),
    maybe_apply_image_edit.s(),
    export_png.s(),
    upload_to_storage.s(),
    report_to_redmine.s(),
)
```

Each step writes its output into a `TaskManifest` dict passed through the chain.

### Task Manifest Schema

```json
{
  "task_id": "redmine-1042",
  "card_type": "hero",
  "product": {
    "sku": "SNK-001",
    "name": "Кроссовки Air X",
    "brand": "BrandName"
  },
  "assets": {
    "main_image_url": "https://...",
    "icons": []
  },
  "text_blocks": {
    "title": "...",
    "description": "...",
    "benefits": []
  },
  "figma": {
    "template_id": null,
    "frame_id": null,
    "fill_map": {}
  },
  "output": {
    "png_url": null,
    "storage_key": null
  },
  "meta": {
    "redmine_issue_id": 1042,
    "job_id": "abc-123",
    "pipeline_step": "normalize_spec",
    "image_edit_enabled": false,
    "errors": []
  }
}
```

### Redmine Integration (`src/content_agent/integrations/redmine/`)

- HTTP client wrapping Redmine REST API v1
- Auth: API key via `X-Redmine-API-Key` header
- Reads: issue fields, custom fields, attachments
- Writes: issue status update, journal note with result URL
- Custom fields schema agreed with team (see `docs/task_management.md`)

### Figma Integration (`src/content_agent/integrations/figma/`)

- `template_registry.json` — маппинг `category → slide_type → (frame_id, fill_map)`
  с реальными node_id из файла `6ftFaqPgnvCbCmyjzxDcKI`
- `FigmaClient` — экспорт PNG: `GET /v1/images/{file_key}?ids={frame_id}&format=png&scale=2`

#### Figma Plugin (rendering engine)

Figma REST API — только чтение. Запись текстовых слоёв и экспорт PNG
производится через **Figma Plugin**, запущенный в Figma Desktop на одной
"render-машине" в офисе.

```
Celery task fill_figma_template
        │
        │  creates FillJob records in DB
        │  (one job per slide)
        ▼
┌─────────────────────┐    GET /api/v1/fill-jobs/pending
│   Figma Desktop     │◄────────────────────────────────── polling every 3s
│   (render machine)  │
│                     │   1. figma.getNodeById(frame_id)
│   PM-RU Plugin      │   2. frame.clone() → workFrame
│   (TypeScript)      │   3. update TEXT layers by path-index
│                     │   4. workFrame.exportAsync({format:"PNG", scale:2})
│                     │   5. POST /api/v1/fill-jobs/{id}/complete  (multipart PNG)
└─────────────────────┘
        │
        │  result_storage_key saved in FillJob
        ▼
Celery polls GET /api/v1/fill-jobs/{id} until status=done
        │
        ▼
manifest.figma.slide_storage_keys populated → next pipeline step
```

**FillJob model** (`src/content_agent/models/fill_job.py`):

| field | type | description |
|-------|------|-------------|
| `id` | UUID | job identifier |
| `job_id` | str | FK → jobs.id |
| `file_key` | str | Figma file key |
| `frame_id` | str | template frame node_id |
| `slide_type` | str | e.g. `preview`, `dimensions` |
| `text_fills` | JSON | `{node_id: text_value}` |
| `status` | enum | pending / processing / done / error / timeout |
| `result_storage_key` | str | storage path of exported PNG |

**Plugin UI:** `figma_plugin/src/ui.html` — кнопка Start, поле Backend URL,
лог последних операций. Запускается из меню Plugins в Figma.

**Template registry:** `src/content_agent/integrations/figma/template_registry.json`
— содержит реальные frame_id и fill_map для категорий `table` (артикул 184109)
и `chair` (артикул 190870).

**Figma file key:** `6ftFaqPgnvCbCmyjzxDcKI`

**Template registry — СТОЛЫ (артикул 184109, эталонный):**
```json
{
  "table_preview":     {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "2:11",  "label": "Превью"},
  "table_dimensions":  {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "2:60",  "label": "Габариты (сложенный)"},
  "table_utp_top":     {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "2:77",  "label": "УТП столешницы"},
  "table_legs":        {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "2:124", "label": "Материал ножек"},
  "table_dims_open":   {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:966", "label": "Размер разложенный (опц.)"},
  "table_mechanism":   {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:1069","label": "Механизм трансформации (опц.)"},
  "table_accent":      {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:924", "label": "Дизайн/акцент (опц.)"}
}
```

**Template registry — СТУЛЬЯ (артикул 190870, эталонный):**
```json
{
  "chair_preview":     {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2387","label": "Превью (вар.1)"},
  "chair_dimensions":  {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2339","label": "Габариты"},
  "chair_material":    {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2104","label": "Материал обивки"},
  "chair_legs":        {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2232","label": "Материал ножек"},
  "chair_seating":     {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2356","label": "Посадка / эргономика"},
  "chair_universal":   {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2145","label": "Универсальное применение (опц.)"},
  "chair_colors":      {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2296","label": "Цветовая палитра"},
  "chair_antiscratch": {"file_key": "6ftFaqPgnvCbCmyjzxDcKI", "frame_id": "4:2322","label": "Антикоготь (опц.)"}
}
```

**Fill map — СТОЛ Превью (frame 2:11):**
```json
{
  "product_title":     "2:20",
  "dimensions_hwl":    "2:21",
  "legs_material":     "2:22",
  "brand":             "2:23",
  "utp_assembly":      "2:42",
  "utp_surface":       "2:53",
  "tabletop_finish":   "2:58",
  "tabletop_material": "2:59"
}
```

**Fill map — СТОЛ Габариты (frame 2:60):**
```json
{
  "width_cm":   "2:69",
  "height_cm":  "2:74"
}
```

**Fill map — СТУЛ Превью (frame 4:2387):**
```json
{
  "brand":           "4:2391",
  "product_type":    "4:2393",
  "max_load":        "4:2394",
  "utp_care":        "4:2418",
  "fabric_type":     "4:2419"
}
```

**Fill map — СТУЛ Габариты (frame 4:2339):**
```json
{
  "width_cm":        "4:2343",
  "depth_cm":        "4:2345",
  "height_cm":       "4:2351",
  "seat_height_cm":  "4:2355"
}
```

> ⚠️ Figma REST API поддерживает только чтение. Запись TEXT-слоёв —
> через `POST /v1/files/{key}/nodes` (beta endpoint). Если этот эндпоинт
> недоступен, альтернатива — рендеринг через Pillow/Cairo с Figma как
> дизайн-референсом (см. `docs/figma_render_approach.md`).

### LLM Layer (`src/content_agent/llm/`)

Abstract `LLMProvider` base class with implementations:
- `OpenAIProvider` — GPT-4o-mini (sufficient for normalization/compression)
- `MockProvider` — for testing without API calls

Two use cases:
1. **`Normalizer`** — converts free-form ТЗ text into structured `product` + `text_blocks` fields
2. **`Compressor`** — shortens `description` and `benefits` to card character limits

Prompts are versioned files in `src/content_agent/llm/prompts/`.

### QA Layer (`src/content_agent/qa/`)

Rule-based validation engine (no LLM). Rules check:
- Required fields presence
- Text length limits per card type
- Image URL reachability
- Asset count constraints (e.g., hero requires exactly 1 main image)
- Card-type-specific constraints

Rules are declarative Python dataclasses, not hardcoded `if/else`.

### Storage Abstraction (`src/content_agent/integrations/storage/`)

Abstract `StorageBackend` with `upload(key, data) → url` interface.
- `S3Backend` — boto3, configured for Yandex Object Storage via `endpoint_url`
- Returns public or pre-signed URL for Redmine report

### Image Edit Layer (`src/content_agent/integrations/image_edit/`)

Optional step. Abstract `ImageEditProvider` with implementations:
- `MockProvider` — pass-through (returns original image)
- `OpenAIDalleProvider` — inpainting stub for Phase 2+

---

## Data Flow

```
Redmine Issue #1042
        │
        ▼
  task_manifest v0    (raw Redmine fields mapped to manifest schema)
        │
        ▼
  task_manifest v1    (validated — QA rules pass)
        │
        ▼
  task_manifest v2    (normalized — structured product/text_blocks via LLM)
        │
        ▼
  task_manifest v3    (compressed — texts fit card limits)
        │
        ▼
  task_manifest v4    (template selected — figma.template_id populated)
        │
        ▼
  task_manifest v5    (figma filled — figma.fill_map populated, Figma updated)
        │
        ▼
  task_manifest v6    (image edit applied if enabled)
        │
        ▼
  task_manifest v7    (PNG exported — output.png_url populated)
        │
        ▼
  task_manifest v8    (uploaded — output.storage_key populated)
        │
        ▼
  Redmine Issue #1042 updated: status=Done, comment with storage URL
```

---

## Card Types (MVP Scope)

| Type | Description | Required Assets | Text Constraints |
|------|-------------|-----------------|-----------------|
| `hero` | Main product shot with title | 1 main image | title ≤ 60 chars |
| `dimensions` | Size/dimension infographic | 1 main image | dimensions: 3–6 entries |
| `colors` | Color variant grid | 2–8 color swatches | color names ≤ 20 chars each |
| `simple_benefit` | Key benefit highlight | 1 icon + 1 image | benefit ≤ 80 chars, title ≤ 60 |

**Out of scope (MVP):** mechanisms, complex functional states, complex interiors, brand slides, custom layout engine, auto-generated icons.

---

## Deployment Architecture

```
docker-compose (local/staging):
  - api          (FastAPI, port 8000)
  - worker       (Celery default queue)
  - worker-img   (Celery image_edit queue, isolated)
  - flower       (Celery monitor, port 5555)
  - postgres     (port 5432)
  - redis        (port 6379)
```

Production: same topology on VMs or Kubernetes, with Yandex Object Storage replacing local S3.

---

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Web framework | FastAPI | Async, Pydantic v2 native, OpenAPI docs |
| Task queue | Celery + Redis | Native chains, Flower monitoring, per-task retry |
| ORM | SQLAlchemy 2.x + Alembic | Typed queries, migrations |
| Validation | Pydantic v2 | Fast, strict typing, JSON schema generation |
| LLM | OpenAI GPT-4o-mini | Cost-efficient for normalization tasks |
| Storage | boto3 + Yandex endpoint | S3-compatible, no vendor lock-in |
| Containerization | Docker Compose | Reproducible local dev and staging |
| Dependency mgmt | uv + pyproject.toml | Fast, modern Python packaging |
