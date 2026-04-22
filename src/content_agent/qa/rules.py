from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from content_agent.schemas.task_manifest import CardType, TaskManifest


@dataclass
class Rule:
    name: str
    card_types: list[CardType] | Literal["all"]
    check: Callable[[TaskManifest], list[str]]
    blocking: bool = True


def _check_required_fields(manifest: TaskManifest) -> list[str]:
    errors = []
    if not manifest.text_blocks.title:
        errors.append("title is required")
    if not manifest.assets.main_image_url:
        errors.append("main_image_url is required")
    return errors


def _check_title_length(manifest: TaskManifest) -> list[str]:
    limit = 60
    title = manifest.text_blocks.title
    if len(title) > limit:
        return [f"title exceeds {limit} chars (got {len(title)})"]
    return []


def _check_description_length(manifest: TaskManifest) -> list[str]:
    limit = 200
    desc = manifest.text_blocks.description
    if len(desc) > limit:
        return [f"description exceeds {limit} chars (got {len(desc)})"]
    return []


def _check_benefit_length(manifest: TaskManifest) -> list[str]:
    limit = 80
    errors = []
    for i, b in enumerate(manifest.text_blocks.benefits):
        if len(b) > limit:
            errors.append(f"benefit[{i}] exceeds {limit} chars (got {len(b)})")
    return errors


def _check_color_count(manifest: TaskManifest) -> list[str]:
    count = len(manifest.text_blocks.color_names)
    if not (2 <= count <= 8):
        return [f"colors card requires 2–8 color names, got {count}"]
    return []


def _check_dimension_count(manifest: TaskManifest) -> list[str]:
    count = len(manifest.text_blocks.dimensions)
    if not (3 <= count <= 6):
        return [f"dimensions card requires 3–6 dimension entries, got {count}"]
    return []


RULES: list[Rule] = [
    Rule(name="required_fields", card_types="all", check=_check_required_fields),
    Rule(name="title_length", card_types="all", check=_check_title_length),
    Rule(
        name="description_length",
        card_types=[CardType.HERO, CardType.SIMPLE_BENEFIT],
        check=_check_description_length,
    ),
    Rule(
        name="benefit_length",
        card_types=[CardType.SIMPLE_BENEFIT],
        check=_check_benefit_length,
    ),
    Rule(
        name="color_count",
        card_types=[CardType.COLORS],
        check=_check_color_count,
    ),
    Rule(
        name="dimension_count",
        card_types=[CardType.DIMENSIONS],
        check=_check_dimension_count,
    ),
]
