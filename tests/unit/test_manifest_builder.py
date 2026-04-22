"""Unit tests for manifest builder."""

import pytest

from content_agent.integrations.redmine.schemas import parse_redmine_issue
from content_agent.workers.tasks.manifest import _build_manifest_from_issue

# Russian field names as used in Redmine
CF_CARD_TYPE = "Тип карточки"
CF_MAIN_IMAGE_URL = "URL главного изображения"
CF_PRODUCT_SKU = "Артикул"
CF_BRIEF_TEXT = "Текст на карточке"
CF_MARKETPLACE = "Маркетплейс"
CF_SEGMENT = "Сегмент инфографики"
CF_COMMENT = "Комментарий"
CF_IMAGE_FORMAT = "Формат изображения"


def _raw_redmine_issue(
    *,
    issue_id: int = 1042,
    subject: str = "Кроссовки Air X",
    description: str | None = "Описание товара",
    card_type: str = "hero",
    main_image_url: str = "https://example.com/image.jpg",
    product_sku: str = "SNK-001",
    brief_text: str = "Лёгкость каждого шага",
    marketplace: str = "Wildberries",
) -> dict:
    issue = {
        "id": issue_id,
        "subject": subject,
        "description": description,
        "custom_fields": [
            {"id": 1, "name": CF_CARD_TYPE, "value": card_type},
            {"id": 2, "name": CF_MAIN_IMAGE_URL, "value": main_image_url},
            {"id": 3, "name": CF_PRODUCT_SKU, "value": product_sku},
            {"id": 4, "name": CF_BRIEF_TEXT, "value": brief_text},
            {"id": 5, "name": CF_MARKETPLACE, "value": marketplace},
        ],
    }
    return {"issue": issue}


def test_parse_redmine_issue() -> None:
    raw = _raw_redmine_issue()
    issue = parse_redmine_issue(raw)
    assert issue.id == 1042
    assert issue.subject == "Кроссовки Air X"
    assert issue.get_custom_field_str(CF_CARD_TYPE) == "hero"
    assert issue.get_custom_field_str(CF_MAIN_IMAGE_URL) == "https://example.com/image.jpg"
    assert issue.get_custom_field_str(CF_PRODUCT_SKU) == "SNK-001"


def test_parse_redmine_issue_unwrapped() -> None:
    raw = _raw_redmine_issue()
    issue = parse_redmine_issue(raw["issue"])
    assert issue.id == 1042


def test_build_manifest_hero() -> None:
    raw = _raw_redmine_issue()
    manifest = _build_manifest_from_issue(raw, "chain-123")
    assert manifest.task_id == "redmine-1042"
    assert manifest.card_type.value == "hero"
    assert manifest.product.sku == "SNK-001"
    assert manifest.product.name == "Кроссовки Air X"
    assert str(manifest.assets.main_image_url) == "https://example.com/image.jpg"
    assert manifest.meta.job_id == "chain-123"
    assert manifest.meta.redmine_issue_id == 1042
    assert manifest.meta.marketplace == "Wildberries"


def test_build_manifest_brief_text_used_as_description() -> None:
    raw = _raw_redmine_issue(brief_text="Краткий текст для карточки")
    manifest = _build_manifest_from_issue(raw, "chain-1")
    assert manifest.text_blocks.description == "Краткий текст для карточки"


def test_build_manifest_all_card_types() -> None:
    for card_type in ("hero", "dimensions", "colors", "simple_benefit"):
        raw = _raw_redmine_issue(card_type=card_type)
        manifest = _build_manifest_from_issue(raw, "chain-1")
        assert manifest.card_type.value == card_type


def test_build_manifest_missing_card_type() -> None:
    raw = _raw_redmine_issue()
    raw["issue"]["custom_fields"] = [
        cf for cf in raw["issue"]["custom_fields"] if cf["name"] != CF_CARD_TYPE
    ]
    with pytest.raises(ValueError, match="card_type is required"):
        _build_manifest_from_issue(raw, "chain-1")


def test_build_manifest_missing_main_image_url() -> None:
    raw = _raw_redmine_issue()
    raw["issue"]["custom_fields"] = [
        cf for cf in raw["issue"]["custom_fields"] if cf["name"] != CF_MAIN_IMAGE_URL
    ]
    with pytest.raises(ValueError, match="URL главного изображения"):
        _build_manifest_from_issue(raw, "chain-1")


def test_build_manifest_invalid_card_type() -> None:
    raw = _raw_redmine_issue(card_type="invalid_type")
    with pytest.raises(ValueError, match="Invalid card_type"):
        _build_manifest_from_issue(raw, "chain-1")


def test_build_manifest_product_sku_fallback() -> None:
    raw = _raw_redmine_issue()
    raw["issue"]["custom_fields"] = [
        cf for cf in raw["issue"]["custom_fields"] if cf["name"] != CF_PRODUCT_SKU
    ]
    raw["issue"]["subject"] = "Product Name"
    manifest = _build_manifest_from_issue(raw, "chain-1")
    assert manifest.product.sku == "Product Name"


def test_redmine_issue_custom_field_list_value() -> None:
    raw = _raw_redmine_issue()
    raw["issue"]["custom_fields"][0]["value"] = ["hero"]
    issue = parse_redmine_issue(raw)
    assert issue.get_custom_field_str(CF_CARD_TYPE) == "hero"


def test_build_manifest_optional_fields() -> None:
    raw = _raw_redmine_issue()
    raw["issue"]["custom_fields"].extend([
        {"id": 6, "name": CF_SEGMENT, "value": "Габариты"},
        {"id": 7, "name": CF_COMMENT, "value": "Фон белый"},
        {"id": 8, "name": CF_IMAGE_FORMAT, "value": "jpg"},
    ])
    manifest = _build_manifest_from_issue(raw, "chain-1")
    assert manifest.meta.segment == "Габариты"
    assert manifest.meta.comment == "Фон белый"
    assert manifest.meta.image_format == "jpg"
