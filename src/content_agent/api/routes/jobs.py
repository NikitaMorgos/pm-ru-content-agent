from celery.result import AsyncResult
from fastapi import APIRouter
from pydantic import BaseModel

from content_agent.workers.celery_app import celery_app

router = APIRouter()


class JobStatusResponse(BaseModel):
    job_id: str
    state: str
    step: str | None = None
    result: dict | None = None
    error: str | None = None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get the current status of a pipeline job."""
    result: AsyncResult = AsyncResult(job_id, app=celery_app)

    step = None
    error = None
    job_result = None

    if result.state == "SUCCESS":
        job_result = result.result
        if isinstance(job_result, dict):
            step = job_result.get("meta", {}).get("pipeline_step")
    elif result.state == "FAILURE":
        error = str(result.result)

    return JobStatusResponse(
        job_id=job_id,
        state=result.state,
        step=step,
        result=job_result if result.state == "SUCCESS" else None,
        error=error,
    )
