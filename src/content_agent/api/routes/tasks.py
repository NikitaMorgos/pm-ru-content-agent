import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from content_agent.workers.pipeline import build_pipeline_chain

logger = structlog.get_logger()
router = APIRouter()


class TriggerRequest(BaseModel):
    redmine_task_id: int


class TriggerResponse(BaseModel):
    job_id: str
    message: str


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_task(request: TriggerRequest) -> TriggerResponse:
    """Trigger the content pipeline for a given Redmine issue ID."""
    pipeline = build_pipeline_chain(request.redmine_task_id)
    result = pipeline.apply_async()

    logger.info("pipeline.triggered", redmine_task_id=request.redmine_task_id, job_id=result.id)

    return TriggerResponse(
        job_id=result.id,
        message=f"Pipeline triggered for Redmine issue #{request.redmine_task_id}",
    )
