import pytest
from pydantic import HttpUrl

from content_agent.qa.validator import run_validation
from content_agent.schemas.task_manifest import (
    AssetInfo,
    CardType,
    ManifestMeta,
    ProductInfo,
    TaskManifest,
    TextBlocks,
)


def make_manifest(
    card_type: CardType = CardType.HERO,
    title: str = "Valid Title",
    description: str = "Valid description.",
    color_names: list[str] | None = None,
    dimensions: list[str] | None = None,
) -> TaskManifest:
    return TaskManifest(
        task_id="redmine-1",
        card_type=card_type,
        product=ProductInfo(sku="TEST-001", name="Test Product"),
        assets=AssetInfo(main_image_url=HttpUrl("https://example.com/img.jpg")),
        text_blocks=TextBlocks(
            title=title,
            description=description,
            color_names=color_names or [],
            dimensions=dimensions or [],
        ),
        meta=ManifestMeta(redmine_issue_id=1, job_id="test"),
    )


def test_valid_hero_manifest(hero_manifest):
    result = run_validation(hero_manifest)
    assert result.is_valid


def test_title_too_long():
    manifest = make_manifest(title="A" * 61)
    result = run_validation(manifest)
    assert not result.is_valid
    assert any("title" in e for e in result.errors)


def test_missing_title():
    manifest = make_manifest(title="")
    result = run_validation(manifest)
    assert not result.is_valid


def test_colors_card_requires_2_to_8_colors():
    manifest = make_manifest(card_type=CardType.COLORS, title="Colors", color_names=["Red"])
    result = run_validation(manifest)
    assert not result.is_valid

    manifest2 = make_manifest(
        card_type=CardType.COLORS,
        title="Colors",
        color_names=["Red", "Blue", "Green"],
    )
    result2 = run_validation(manifest2)
    assert result2.is_valid


def test_dimensions_card_requires_3_to_6_entries():
    manifest = make_manifest(
        card_type=CardType.DIMENSIONS,
        title="Dims",
        dimensions=["L: 30cm", "W: 20cm"],
    )
    result = run_validation(manifest)
    assert not result.is_valid

    manifest2 = make_manifest(
        card_type=CardType.DIMENSIONS,
        title="Dims",
        dimensions=["L: 30cm", "W: 20cm", "H: 10cm"],
    )
    result2 = run_validation(manifest2)
    assert result2.is_valid
