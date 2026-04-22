# Task Management — PM-RU Content Agent

## Overview

Every Redmine task that enters the system gets a corresponding **task folder** in `project_tasks/`.
Task folders serve as the local context store — they preserve full state across agent sessions,
human context switches, and pipeline resumptions.

---

## Task Folder Location & Naming

```
project_tasks/
└── {task_slug}/
    ├── tasks/
    ├── jobs/
    ├── breadcrumbs/
    ├── docs/
    ├── status.md
    └── plan.md
```

### Slug Format

```
redmine-{issue_id}-{card_type}-{product_slug}
```

| Component | Source | Rules |
|-----------|--------|-------|
| `redmine-{issue_id}` | Redmine issue ID | Required, numeric |
| `{card_type}` | Custom field `card_type` | hero / dimensions / colors / simple_benefit |
| `{product_slug}` | Product name, kebab-cased | Max 30 chars, ASCII only, no spaces |

**Examples:**
```
redmine-1042-hero-sneaker-air-x
redmine-1055-dimensions-backpack-pro
redmine-1071-colors-tshirt-basic
redmine-1088-simple-benefit-headphones-z
```

---

## Folder Contents

### `tasks/`

Machine-generated files created by the pipeline.

```
tasks/
└── task_manifest.json    # Full TaskManifest at current pipeline state
```

`task_manifest.json` is updated by each pipeline step (versioned by `meta.pipeline_step` field).
Agents can read this to understand the current manifest state without querying the DB.

### `jobs/`

Celery job tracking files.

```
jobs/
└── celery_{job_id}.json    # Job state snapshot
```

**`celery_{job_id}.json` format:**
```json
{
  "job_id": "abc-123-def-456",
  "celery_task_id": "xyz-789",
  "state": "RUNNING",
  "current_step": "fill_figma_template",
  "steps_completed": ["fetch_redmine_task", "build_task_manifest", "validate_manifest",
                       "normalize_spec", "compress_texts", "select_figma_template"],
  "started_at": "2026-03-16T10:00:00Z",
  "updated_at": "2026-03-16T10:04:22Z",
  "error": null
}
```

### `breadcrumbs/`

Append-only chronological event log. One file per significant event.

```
breadcrumbs/
├── 2026-03-16T10-00-00_created.md
├── 2026-03-16T10-00-05_ingest.md
├── 2026-03-16T10-00-12_manifest.md
├── 2026-03-16T10-00-18_validate.md
├── 2026-03-16T10-01-30_normalize.md
├── 2026-03-16T10-02-10_compress.md
├── 2026-03-16T10-03-00_template_select.md
├── 2026-03-16T10-04-22_figma_fill.md
├── 2026-03-16T10-05-00_export.md
├── 2026-03-16T10-05-15_upload.md
└── 2026-03-16T10-05-20_reported.md
```

**Breadcrumb filename format:** `{YYYY-MM-DDTHH-MM-SS}_{step_name}.md`

**Breadcrumb file template:**
```markdown
# Breadcrumb: {step_name}
- timestamp: {ISO 8601}
- duration_ms: {number}
- status: success | warning | error

## Input Summary
{key fields from manifest input}

## Output Summary
{key fields added/modified in manifest}

## Notes
{optional: edge cases, retries, warnings}
```

**Example `2026-03-16T10-04-22_figma_fill.md`:**
```markdown
# Breadcrumb: fill_figma_template
- timestamp: 2026-03-16T10:04:22Z
- duration_ms: 1840
- status: success

## Input Summary
- template_id: figma:abc123/1:23
- fill_map keys: TEXT_TITLE, TEXT_DESCRIPTION, IMG_MAIN

## Output Summary
- fill_map populated: 3 layers updated
- figma_node_version: 42

## Notes
- TEXT_DESCRIPTION was truncated to 198 chars (limit: 200)
```

### `docs/`

Human-authored context files.

```
docs/
├── notes.md          # Edge cases, designer feedback, manual overrides, decisions
└── {anything}.md     # Additional docs as needed
```

**`notes.md`** is free-form. Use it for:
- Edge cases encountered during this task
- Feedback from designer or PM
- Manual overrides applied (e.g., "used fallback template v1.1 because v1.2 had broken layer")
- Decisions made and their rationale

### `status.md`

Current task state at a glance. Updated whenever state changes.

**Template:**
```markdown
# Status: {task_slug}

## Current State
- state: pending | in_progress | blocked | done | failed
- step: {current_pipeline_step or "—"}
- updated: {ISO 8601}

## Redmine
- issue_id: {number}
- issue_url: {url}
- card_type: {hero|dimensions|colors|simple_benefit}
- product: {product name}

## Result
- result_url: {PNG URL or "—"}
- storage_key: {S3 key or "—"}

## Blockers
{list any blockers, or "none"}
```

**Example:**
```markdown
# Status: redmine-1042-hero-sneaker-air-x

## Current State
- state: in_progress
- step: fill_figma_template
- updated: 2026-03-16T10:04:00Z

## Redmine
- issue_id: 1042
- issue_url: https://redmine.example.com/issues/1042
- card_type: hero
- product: Кроссовки Air X

## Result
- result_url: —
- storage_key: —

## Blockers
none
```

### `plan.md`

Living checklist for this specific task. Created at task start, updated as steps complete.

**Template:**
```markdown
# Plan: {task_slug}

## Pipeline Checklist
- [ ] 1. Fetch Redmine task
- [ ] 2. Build task manifest
- [ ] 3. Validate manifest
- [ ] 4. Normalize spec (LLM)
- [ ] 5. Compress texts (LLM)
- [ ] 6. Select Figma template
- [ ] 7. Fill Figma template
- [ ] 8. Apply image edit (optional)
- [ ] 9. Export PNG
- [ ] 10. Upload to storage
- [ ] 11. Report to Redmine

## Special Notes
{any task-specific requirements or concerns}

## Definition of Done
- [ ] PNG exported at 2x resolution
- [ ] All QA rules pass (no blocking errors)
- [ ] Redmine issue status updated to Done
- [ ] Result URL in Redmine journal note
```

---

## Creating a Task Folder

### Automated (preferred)

The pipeline creates the task folder automatically when `build_task_manifest` runs.
The folder slug is derived from manifest fields.

### Manual (for agent/human work)

```bash
TASK_SLUG="redmine-1042-hero-sneaker-air-x"
BASE="project_tasks/$TASK_SLUG"

mkdir -p $BASE/tasks $BASE/jobs $BASE/breadcrumbs $BASE/docs
touch $BASE/status.md $BASE/plan.md $BASE/docs/notes.md
```

Or use the helper script (Phase 7):
```bash
uv run python -m content_agent.cli create-task-folder \
  --redmine-id 1042 \
  --card-type hero \
  --product-slug sneaker-air-x
```

---

## Picking Up a Task (Agent Workflow)

When resuming work on a task:

1. List task folders: `ls project_tasks/`
2. Find the folder by Redmine issue ID or product slug
3. Read `status.md` → understand current state
4. Read `plan.md` → see what's done and what remains
5. Read latest breadcrumb in `breadcrumbs/` → see last action
6. Read `tasks/task_manifest.json` → inspect current manifest
7. Read `docs/notes.md` → check for edge cases or special context
8. Proceed with next step

---

## Redmine Custom Fields Schema

Fields are configured in Redmine in Russian. Internal code keys are listed for developer reference.

### Обязательные поля (Required)

| Название в Redmine | Внутренний ключ | Тип | Значения / формат | Примечание |
|-------------------|-----------------|-----|-------------------|------------|
| `Тип карточки` | `card_type` | List | hero, dimensions, colors, simple_benefit | Пайплайн останавливается если отсутствует |
| `URL главного изображения` | `main_image_url` | Text | HTTPS URL | Должен быть публично доступен |
| `Артикул` | `product_sku` | Text | например, SNK-001 | Используется в storage key |

### Опциональные поля (Optional — заполняет менеджер)

| Название в Redmine | Внутренний ключ | Тип | Описание |
|-------------------|-----------------|-----|---------|
| `Вариант` | `variant` | Text | Вариант товара (цвет, размер и т.п.); уточняет артикул |
| `Текст на карточке` | `brief_text` | Text | Основной текст/описание для карточки |
| `Цветовое решение` | `color_scheme` | Text | Описание цветовых решений (для типа colors) |
| `Сегмент инфографики` | `segment` | Text/List | Сегмент инфографики (для типа dimensions) |
| `Маркетплейс` | `marketplace` | Text/List | Целевой маркетплейс |
| `Номер изображения в карточке` | `image_number` | Text | Номер слота изображения |
| `Формат изображения` | `image_format` | Text/List | png / jpg (по умолчанию png) |
| `Комментарий` | `comment` | Text | Заметки менеджера (не попадают в карточку) |
| `Фотореференс` | `photo_reference_url` | Text | URL фото-референса |

### Автоматические поля (Auto — заполняет пайплайн)

| Название в Redmine | Внутренний ключ | Тип | Примечание |
|-------------------|-----------------|-----|-----------|
| `ID` | `content_agent_job_id` | Text | Записывается при запуске пайплайна |
| `Рендер` | `render_url` | Text | URL результирующего PNG (записывается при успехе) |

Поля с пометкой **Auto** заполняются пайплайном автоматически — не редактировать вручную.

---

## Task Folder Lifecycle

```
Redmine Issue Created
        │
        ▼
project_tasks/{slug}/ created
status.md: state=pending
        │
        ▼
Pipeline triggered (POST /tasks/trigger)
status.md: state=in_progress
jobs/celery_{id}.json created
        │
        ▼
Each pipeline step completes
breadcrumbs/{timestamp}_{step}.md appended
tasks/task_manifest.json updated
plan.md checklist item ticked
        │
        ├──[success]──▶ status.md: state=done, result_url=...
        │                Redmine: status=Done, journal note with URL
        │
        └──[failure]──▶ status.md: state=failed, blockers=...
                         Redmine: journal note with error details
                         breadcrumbs/{timestamp}_error.md created
```

---

## Rules for Agents

1. **Always create the task folder before starting pipeline work** — never work without context
2. **Always update `status.md`** when state changes (start, blocked, done, failed)
3. **Breadcrumbs are append-only** — never delete or modify existing breadcrumb files
4. **`tasks/task_manifest.json` reflects current state** — update it after each step
5. **`docs/notes.md` is for decisions** — document any deviation from standard flow
6. **One Redmine issue = one task folder** — never share a folder across multiple issues
7. **Slug must be stable** — do not rename the folder after creation
