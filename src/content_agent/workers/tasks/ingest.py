"""Ingest task: fetch Redmine issue."""

import structlog

from content_agent.integrations.redmine.client import RedmineClient
from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="content_agent.workers.tasks.ingest.fetch_redmine_task")
def fetch_redmine_task(self, redmine_task_id: int) -> dict:  # type: ignore[override]
    """
    Fetch Redmine issue and return raw data + chain head id for downstream tasks.
    """
    logger.info("ingest.start", redmine_task_id=redmine_task_id)
    client = RedmineClient()
    try:
        data = client.get_issue(redmine_task_id)
        chain_head_id = self.request.id
        result = {"raw_issue": data, "chain_head_id": chain_head_id}
        logger.info("ingest.done", redmine_task_id=redmine_task_id)
        return result
    finally:
        client.close()
