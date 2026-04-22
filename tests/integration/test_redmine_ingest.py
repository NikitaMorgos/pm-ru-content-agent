"""Integration tests for Redmine ingest + manifest (mocked HTTP)."""

import pytest
import respx
from httpx import Response

from content_agent.workers.celery_app import celery_app
from content_agent.workers.tasks.ingest import fetch_redmine_task
from content_agent.workers.tasks.manifest import build_task_manifest


@pytest.fixture(autouse=True)
def celery_eager() -> None:
    """Run Celery tasks synchronously (no worker needed)."""
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False


@respx.mock
def test_fetch_and_build_manifest() -> None:
    """Test full ingest + manifest flow with mocked Redmine API."""
    redmine_url = "https://redmine.example.com"
    respx.get(f"{redmine_url}/issues/1042.json").mock(
        return_value=Response(
            200,
            json={
                "issue": {
                    "id": 1042,
                    "subject": "Кроссовки Air X",
                    "description": "Описание",
                    "custom_fields": [
                        {"id": 1, "name": "Тип карточки", "value": "hero"},
                        {"id": 2, "name": "URL главного изображения", "value": "https://example.com/img.jpg"},
                        {"id": 3, "name": "Артикул", "value": "SNK-001"},
                        {"id": 4, "name": "Маркетплейс", "value": "Wildberries"},
                    ],
                }
            },
        )
    )

    ingest_result = fetch_redmine_task(1042)
    assert "raw_issue" in ingest_result
    assert "chain_head_id" in ingest_result

    manifest_dict = build_task_manifest(ingest_result)
    assert manifest_dict["task_id"] == "redmine-1042"
    assert manifest_dict["card_type"] == "hero"
    assert manifest_dict["product"]["sku"] == "SNK-001"
    # In eager mode chain_head_id may be None; manifest uses fallback "unknown"
    assert manifest_dict["meta"]["job_id"] in (ingest_result.get("chain_head_id"), "unknown")
