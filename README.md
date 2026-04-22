# PM-RU Content Agent

Automated pipeline for assembling marketplace product cards.

**Architecture:** Redmine → Celery pipeline → Figma → S3 → Redmine  
**MVP card types:** hero, dimensions, colors, simple_benefit

## Quick Start

```bash
# 1. Install dependencies
pip install uv
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start all services
docker-compose up

# 4. Run DB migrations
uv run alembic upgrade head

# 5. Trigger a pipeline
curl -X POST http://localhost:8000/tasks/trigger \
  -H "Content-Type: application/json" \
  -d '{"redmine_task_id": 1042}'

# 6. Check job status
curl http://localhost:8000/jobs/{job_id}
```

## Monitoring

- **Flower** (Celery monitor): http://localhost:5555
- **API docs** (Swagger): http://localhost:8000/docs

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/content_agent/
```

## Documentation

- [Architecture](docs/architecture.md)
- [Phased Plan](docs/phased_plan.md)
- [Repo Structure](docs/repo_structure.md)
- [Task Management](docs/task_management.md)
- [AGENTS.md](AGENTS.md) — read this first if you're an AI agent
