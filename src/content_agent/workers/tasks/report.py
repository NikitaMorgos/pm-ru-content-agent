import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.report.report_to_redmine")
def report_to_redmine(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Update Redmine issue: set status to Done, add journal note with result URL."""
    logger.info("report.start")
    # TODO: call RedmineClient.update_issue(issue_id, status=Done, custom_fields={result_url})
    # TODO: call RedmineClient.add_journal(issue_id, note=f"Card exported: {png_url}")
    raise NotImplementedError("report_to_redmine not yet implemented")
