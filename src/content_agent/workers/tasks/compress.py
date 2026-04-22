import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.compress.compress_texts")
def compress_texts(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Use LLM to compress text fields to card character limits."""
    logger.info("compress.start")
    # TODO: call LLMProvider.compressor.compress_text() for title, description, benefits
    raise NotImplementedError("compress_texts not yet implemented")
