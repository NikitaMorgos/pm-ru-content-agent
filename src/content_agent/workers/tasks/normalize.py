import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.normalize.normalize_spec")
def normalize_spec(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Use LLM to normalize free-form ТЗ text into structured manifest fields."""
    logger.info("normalize.start")
    # TODO: call LLMProvider.normalizer.normalize_spec(raw_text) → update manifest
    raise NotImplementedError("normalize_spec not yet implemented")
