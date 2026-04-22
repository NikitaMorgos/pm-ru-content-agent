import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.storage.upload_to_storage")
def upload_to_storage(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Download PNG from Figma CDN and upload to S3-compatible storage."""
    logger.info("storage.upload.start")
    # TODO: download png from manifest.output.png_url
    # TODO: build storage key: exports/{card_type}/{redmine_id}/{timestamp}.png
    # TODO: call StorageBackend.upload(key, data) → permanent URL
    # TODO: set manifest.output.storage_key and manifest.output.png_url
    raise NotImplementedError("upload_to_storage not yet implemented")
