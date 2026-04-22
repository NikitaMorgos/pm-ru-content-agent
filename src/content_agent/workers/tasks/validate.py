import structlog

from content_agent.qa.validator import run_validation
from content_agent.schemas.task_manifest import TaskManifest
from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.validate.validate_manifest")
def validate_manifest(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Run QA rules against the manifest. Raises on blocking errors."""
    manifest = TaskManifest.model_validate(manifest_dict)
    manifest.meta.pipeline_step = "validate_manifest"

    result = run_validation(manifest)

    if result.warnings:
        manifest.meta.warnings.extend(result.warnings)
        logger.warning("validate.warnings", warnings=result.warnings)

    if not result.is_valid:
        logger.error("validate.failed", errors=result.errors)
        raise ValueError(f"Manifest validation failed: {result.errors}")

    logger.info("validate.passed")
    return manifest.model_dump(mode="json")
