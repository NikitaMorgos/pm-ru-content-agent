import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="content_agent.workers.tasks.image_edit.maybe_apply_image_edit",
    queue="image_edit",
)
def maybe_apply_image_edit(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Optionally apply image edit if manifest.meta.image_edit_enabled is True."""
    if not manifest_dict.get("meta", {}).get("image_edit_enabled", False):
        logger.info("image_edit.skipped")
        return manifest_dict

    logger.info("image_edit.start")
    # TODO: call ImageEditProvider.edit(main_image_url, prompt) → update manifest
    raise NotImplementedError("image_edit not yet implemented")
