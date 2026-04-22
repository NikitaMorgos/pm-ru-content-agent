"""Manifest task: build TaskManifest from raw Redmine issue."""

import structlog
from pydantic import HttpUrl

from content_agent.integrations.redmine.client import (
    CF_BRIEF_TEXT,
    CF_CARD_TYPE,
    CF_COLOR_SCHEME,
    CF_COMMENT,
    CF_IMAGE_FORMAT,
    CF_IMAGE_NUMBER,
    CF_MAIN_IMAGE_URL,
    CF_MARKETPLACE,
    CF_PHOTO_REFERENCE_URL,
    CF_PRODUCT_SKU,
    CF_SEGMENT,
    CF_VARIANT,
)
from content_agent.integrations.redmine.schemas import parse_redmine_issue
from content_agent.schemas.task_manifest import (
    AssetInfo,
    CardType,
    FigmaInfo,
    ManifestMeta,
    OutputInfo,
    ProductInfo,
    TaskManifest,
    TextBlocks,
)
from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


def _parse_card_type(value: str | None) -> CardType:
    """Parse card_type string to enum."""
    if not value:
        raise ValueError("card_type is required (Тип карточки)")
    v = value.lower().strip()
    try:
        return CardType(v)
    except ValueError as err:
        raise ValueError(
            f"Invalid card_type: '{value}'. Must be one of: hero, dimensions, colors, simple_benefit"
        ) from err


def _build_manifest_from_issue(raw_data: dict, chain_head_id: str) -> TaskManifest:
    """Build TaskManifest from raw Redmine API response."""
    issue = parse_redmine_issue(raw_data)

    # --- Required fields ---
    card_type_str = issue.get_custom_field_str(CF_CARD_TYPE)
    card_type = _parse_card_type(card_type_str)

    main_image_url_str = issue.get_custom_field_str(CF_MAIN_IMAGE_URL)
    if not main_image_url_str:
        raise ValueError(f"'{CF_MAIN_IMAGE_URL}' custom field is required")
    main_image_url = HttpUrl(main_image_url_str)

    product_sku = issue.get_custom_field_str(CF_PRODUCT_SKU) or issue.subject[:50] or "UNKNOWN"
    product_name = issue.subject or "Untitled"

    # --- Optional text fields ---
    variant = issue.get_custom_field_str(CF_VARIANT)
    brief_text = issue.get_custom_field_str(CF_BRIEF_TEXT) or ""
    color_scheme = issue.get_custom_field_str(CF_COLOR_SCHEME)
    segment = issue.get_custom_field_str(CF_SEGMENT)
    marketplace = issue.get_custom_field_str(CF_MARKETPLACE)
    image_number = issue.get_custom_field_str(CF_IMAGE_NUMBER)
    comment = issue.get_custom_field_str(CF_COMMENT)
    photo_reference_url = issue.get_custom_field_str(CF_PHOTO_REFERENCE_URL)
    image_format = issue.get_custom_field_str(CF_IMAGE_FORMAT) or "png"

    task_id = f"redmine-{issue.id}"

    return TaskManifest(
        task_id=task_id,
        card_type=card_type,
        product=ProductInfo(sku=product_sku, name=product_name),
        assets=AssetInfo(main_image_url=main_image_url),
        text_blocks=TextBlocks(
            title=product_name,
            description=brief_text or (issue.description or "")[:500],
        ),
        figma=FigmaInfo(),
        output=OutputInfo(),
        meta=ManifestMeta(
            redmine_issue_id=issue.id,
            job_id=chain_head_id,
            pipeline_step="build_task_manifest",
            variant=variant,
            marketplace=marketplace,
            segment=segment,
            image_number=image_number,
            image_format=image_format.lower(),
            color_scheme=color_scheme,
            comment=comment,
            photo_reference_url=photo_reference_url,
        ),
    )


@celery_app.task(bind=True, name="content_agent.workers.tasks.manifest.build_task_manifest")
def build_task_manifest(self, ingest_result: dict) -> dict:  # type: ignore[override]
    """
    Build a TaskManifest dict from ingest result (raw_issue + chain_head_id).
    """
    logger.info("manifest.start")
    raw_issue = ingest_result.get("raw_issue")
    chain_head_id = ingest_result.get("chain_head_id") or "unknown"

    if not raw_issue:
        raise ValueError("ingest_result must contain raw_issue")

    manifest = _build_manifest_from_issue(raw_issue, chain_head_id)
    result = manifest.model_dump(mode="json")
    logger.info("manifest.done", task_id=manifest.task_id, card_type=manifest.card_type)
    return result
