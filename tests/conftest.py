"""Pytest configuration. Set env vars before any config-dependent imports."""

import os

# Minimal env for tests — must run before content_agent.config is loaded
for key, default in [
    ("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/content_agent"),
    ("REDIS_URL", "redis://localhost:6379/0"),
    ("REDMINE_BASE_URL", "https://redmine.example.com"),
    ("REDMINE_API_KEY", "test-key"),
    ("FIGMA_ACCESS_TOKEN", "test-token"),
    ("FIGMA_TEMPLATE_REGISTRY_PATH", "config/template_registry.json"),
    ("STORAGE_ENDPOINT_URL", "https://storage.example.com"),
    ("STORAGE_BUCKET", "test-bucket"),
    ("AWS_ACCESS_KEY_ID", "test-ak"),
    ("AWS_SECRET_ACCESS_KEY", "test-sk"),
    ("OPENAI_API_KEY", "test-ok"),
    ("API_KEY", "test-api-key"),
]:
    os.environ.setdefault(key, default)

import pytest
from pydantic import HttpUrl

from content_agent.schemas.task_manifest import (
    AssetInfo,
    CardType,
    ManifestMeta,
    ProductInfo,
    TaskManifest,
    TextBlocks,
)


@pytest.fixture
def hero_manifest() -> TaskManifest:
    return TaskManifest(
        task_id="redmine-1042",
        card_type=CardType.HERO,
        product=ProductInfo(sku="SNK-001", name="Кроссовки Air X", brand="BrandX"),
        assets=AssetInfo(main_image_url=HttpUrl("https://example.com/image.jpg")),
        text_blocks=TextBlocks(
            title="Кроссовки Air X — лёгкость каждого шага",
            description="Инновационная подошва обеспечивает максимальный комфорт.",
        ),
        meta=ManifestMeta(redmine_issue_id=1042, job_id="test-job-001"),
    )


@pytest.fixture
def colors_manifest() -> TaskManifest:
    return TaskManifest(
        task_id="redmine-1055",
        card_type=CardType.COLORS,
        product=ProductInfo(sku="TSH-001", name="Футболка Basic"),
        assets=AssetInfo(main_image_url=HttpUrl("https://example.com/tshirt.jpg")),
        text_blocks=TextBlocks(
            title="Футболка Basic",
            color_names=["Белый", "Чёрный", "Серый", "Синий"],
        ),
        meta=ManifestMeta(redmine_issue_id=1055, job_id="test-job-002"),
    )
