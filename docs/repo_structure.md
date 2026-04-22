# Repository Structure — PM-RU Content Agent

## Root Layout

```
pm-ru-content-agent/
│
├── AGENTS.md                          # Agent-friendly project guide (always read first)
├── README.md                          # Quick start for humans
├── pyproject.toml                     # Python deps, tool config (uv)
├── .env.example                       # All env vars documented (copy → .env)
├── docker-compose.yml                 # Local dev: api, worker, worker-img, flower, postgres, redis
│
├── alembic/                           # DB migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
│
├── src/
│   └── content_agent/                 # Main Python package
│       ├── __init__.py
│       ├── main.py                    # FastAPI app factory + lifespan
│       ├── config.py                  # pydantic-settings: all config in one place
│       │
│       ├── api/                       # HTTP layer
│       │   ├── __init__.py
│       │   ├── deps.py                # FastAPI dependencies (DB session, auth)
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── tasks.py           # POST /tasks/trigger
│       │       ├── jobs.py            # GET /jobs/{job_id}
│       │       └── webhooks.py        # POST /webhooks/redmine
│       │
│       ├── models/                    # SQLAlchemy ORM models (DB tables)
│       │   ├── __init__.py
│       │   ├── job.py                 # Job: id, state, step, created_at, updated_at
│       │   └── task_manifest.py       # TaskManifestRecord: job_id FK, manifest JSON
│       │
│       ├── schemas/                   # Pydantic v2 schemas (validation + serialization)
│       │   ├── __init__.py
│       │   ├── task_manifest.py       # TaskManifest, CardType enum, ProductInfo, etc.
│       │   ├── redmine.py             # RedmineIssue, RedmineCustomField
│       │   └── figma.py               # FigmaTemplate, FillMap, FigmaExportResult
│       │
│       ├── workers/                   # Celery application
│       │   ├── __init__.py
│       │   ├── celery_app.py          # Celery instance, queue definitions, config
│       │   ├── pipeline.py            # build_pipeline_chain(task_id) → chain
│       │   └── tasks/
│       │       ├── __init__.py
│       │       ├── ingest.py          # fetch_redmine_task
│       │       ├── manifest.py        # build_task_manifest
│       │       ├── validate.py        # validate_manifest
│       │       ├── normalize.py       # normalize_spec (LLM)
│       │       ├── compress.py        # compress_texts (LLM)
│       │       ├── template.py        # select_figma_template + fill_figma_template
│       │       ├── image_edit.py      # maybe_apply_image_edit (optional)
│       │       ├── export.py          # export_png
│       │       ├── storage.py         # upload_to_storage
│       │       └── report.py          # report_to_redmine
│       │
│       ├── integrations/              # External service clients
│       │   ├── __init__.py
│       │   │
│       │   ├── redmine/
│       │   │   ├── __init__.py
│       │   │   ├── client.py          # RedmineClient: get_issue, update_issue, add_journal
│       │   │   └── schemas.py         # IssueResponse, CustomField
│       │   │
│       │   ├── figma/
│       │   │   ├── __init__.py
│       │   │   ├── client.py          # FigmaClient: get_file, update_nodes, export_image
│       │   │   ├── template_registry.py  # CARD_TYPE → (file_key, frame_id, version)
│       │   │   └── filler.py          # FigmaFiller: manifest → fill_map → API calls
│       │   │
│       │   ├── storage/
│       │   │   ├── __init__.py
│       │   │   ├── base.py            # StorageBackend ABC: upload(key, data) → url
│       │   │   └── s3.py              # S3Backend (boto3, Yandex Object Storage)
│       │   │
│       │   └── image_edit/
│       │       ├── __init__.py
│       │       ├── base.py            # ImageEditProvider ABC: edit(image_url, prompt) → url
│       │       └── providers/
│       │           ├── __init__.py
│       │           ├── mock.py        # Pass-through mock
│       │           └── openai_dalle.py  # DALL-E inpaint (Phase 2+)
│       │
│       ├── llm/                       # LLM abstraction layer
│       │   ├── __init__.py
│       │   ├── base.py                # LLMProvider ABC: complete(system, user) → str
│       │   ├── providers/
│       │   │   ├── __init__.py
│       │   │   ├── openai.py          # OpenAIProvider (async)
│       │   │   └── mock.py            # MockProvider (deterministic, for tests)
│       │   ├── prompts/               # Versioned prompt templates
│       │   │   ├── normalize_v1.txt
│       │   │   └── compress_v1.txt
│       │   ├── normalizer.py          # normalize_spec(raw) → ProductInfo + TextBlocks
│       │   └── compressor.py          # compress_text(text, max_chars) → str
│       │
│       ├── qa/                        # Rule-based QA engine
│       │   ├── __init__.py
│       │   ├── rules.py               # Rule dataclasses, per-card-type rule sets
│       │   └── validator.py           # run_validation(manifest) → ValidationResult
│       │
│       └── db/                        # Database layer
│           ├── __init__.py
│           ├── session.py             # async_sessionmaker, get_session dependency
│           └── base.py                # SQLAlchemy DeclarativeBase
│
├── project_tasks/                     # Per-task context directories (see task_management.md)
│   └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # pytest fixtures (async client, mock services)
│   ├── unit/
│   │   ├── test_manifest_builder.py
│   │   ├── test_qa_rules.py
│   │   ├── test_compressor.py
│   │   ├── test_normalizer.py
│   │   ├── test_figma_filler.py
│   │   └── test_storage.py
│   └── integration/
│       ├── test_pipeline_e2e.py       # Full chain with mocked external APIs
│       ├── test_redmine_client.py
│       └── test_api_routes.py
│
└── docs/
    ├── architecture.md                # System design (this project's main arch doc)
    ├── phased_plan.md                 # 7-phase implementation plan
    ├── repo_structure.md              # This file
    ├── task_management.md             # project_tasks/ folder conventions
    ├── figma_conventions.md           # Figma layer naming standards (Phase 4)
    └── runbook.md                     # Operational procedures (Phase 7)
```

---

## Module Responsibilities

### `config.py`

Single source of truth for all configuration. All env vars read once here.

```python
class Settings(BaseSettings):
    # Database
    database_url: str
    # Redis / Celery
    redis_url: str
    # Redmine
    redmine_base_url: str
    redmine_api_key: SecretStr
    # Figma
    figma_access_token: SecretStr
    figma_template_registry_path: str = "config/template_registry.json"
    # Storage
    storage_endpoint_url: str
    storage_bucket: str
    aws_access_key_id: SecretStr
    aws_secret_access_key: SecretStr
    # LLM
    openai_api_key: SecretStr
    llm_provider: Literal["openai", "mock"] = "openai"
    # Image Edit
    image_edit_provider: Literal["mock", "openai_dalle"] = "mock"
    # API
    api_key: SecretStr
```

### `workers/pipeline.py`

Builds the Celery chain. Centralizes pipeline construction so steps can be reordered or conditionally included.

```python
def build_pipeline_chain(redmine_task_id: int) -> chain:
    return chain(
        fetch_redmine_task.s(redmine_task_id),
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

### `qa/rules.py`

Rules are declarative, not procedural.

```python
@dataclass
class Rule:
    name: str
    card_types: list[CardType] | Literal["all"]
    check: Callable[[TaskManifest], list[str]]  # returns error messages

RULES: list[Rule] = [
    Rule(name="required_fields", card_types="all", check=check_required_fields),
    Rule(name="title_length", card_types="all", check=check_title_length),
    ...
]
```

### `integrations/*/base.py` pattern

All external integrations follow ABC pattern for easy mock/swap:

```python
class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Upload data and return public URL."""
```

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Python files | `snake_case.py` | `template_registry.py` |
| Classes | `PascalCase` | `FigmaFiller` |
| Celery tasks | `snake_case` function names | `fetch_redmine_task` |
| Pydantic models | `PascalCase` | `TaskManifest` |
| DB table names | `snake_case` plural | `jobs`, `task_manifests` |
| Env vars | `UPPER_SNAKE_CASE` | `FIGMA_ACCESS_TOKEN` |
| project_tasks slugs | `redmine-{id}-{card_type}-{product_slug}` | `redmine-1042-hero-sneaker-x` |

---

## Test Strategy

- **Unit tests**: all business logic with mocked external dependencies
- **Integration tests**: pipeline with HTTP-mocked external APIs (respx / responses)
- **No real API calls in CI** — all providers have mock implementations
- Minimum coverage target: 80% on `qa/`, `llm/`, `schemas/`

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=content_agent --cov-report=term-missing

# Run only unit tests
uv run pytest tests/unit/
```
