import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.export.export_png")
def export_png(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Export the filled Figma frame as PNG via Figma /images API."""
    logger.info("export.start")
    # TODO: call FigmaClient.export_image(file_key, frame_id) → bytes
    # TODO: set manifest.output.png_url (temp URL from Figma CDN)
    raise NotImplementedError("export_png not yet implemented")
