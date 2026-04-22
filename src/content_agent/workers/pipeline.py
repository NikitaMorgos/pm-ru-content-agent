from celery import chain

from content_agent.workers.tasks.compress import compress_texts
from content_agent.workers.tasks.export import export_png
from content_agent.workers.tasks.image_edit import maybe_apply_image_edit
from content_agent.workers.tasks.ingest import fetch_redmine_task
from content_agent.workers.tasks.manifest import build_task_manifest
from content_agent.workers.tasks.normalize import normalize_spec
from content_agent.workers.tasks.report import report_to_redmine
from content_agent.workers.tasks.storage import upload_to_storage
from content_agent.workers.tasks.template import fill_figma_template, select_figma_template
from content_agent.workers.tasks.validate import validate_manifest


def build_pipeline_chain(redmine_task_id: int) -> chain:
    """Build the full Celery pipeline chain for a given Redmine task ID."""
    return chain(
        fetch_redmine_task.s(redmine_task_id),
        build_task_manifest.s(),
        validate_manifest.s(),
        normalize_spec.s(),
        compress_texts.s(),
        select_figma_template.s(),
        fill_figma_template.s(),
        maybe_apply_image_edit.s(),
        export_png.s(),
        upload_to_storage.s(),
        report_to_redmine.s(),
    )
