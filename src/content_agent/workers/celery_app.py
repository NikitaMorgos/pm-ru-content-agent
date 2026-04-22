from celery import Celery

from content_agent.config import settings

celery_app = Celery(
    "content_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "content_agent.workers.tasks.ingest",
        "content_agent.workers.tasks.manifest",
        "content_agent.workers.tasks.validate",
        "content_agent.workers.tasks.normalize",
        "content_agent.workers.tasks.compress",
        "content_agent.workers.tasks.template",
        "content_agent.workers.tasks.image_edit",
        "content_agent.workers.tasks.export",
        "content_agent.workers.tasks.storage",
        "content_agent.workers.tasks.report",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    task_routes={
        "content_agent.workers.tasks.image_edit.*": {"queue": "image_edit"},
        "*": {"queue": "default"},
    },
    task_default_retry_delay=30,
    task_max_retries=3,
    task_acks_late=True,
)
