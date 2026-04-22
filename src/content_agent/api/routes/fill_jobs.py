"""API endpoints consumed by the Figma plugin (render workstation).

Flow:
  plugin  →  GET  /fill-jobs/pending          – claim next pending job
  plugin  →  POST /fill-jobs/{id}/complete    – submit exported PNG
  plugin  →  POST /fill-jobs/{id}/error       – report failure
  backend →  GET  /fill-jobs/{id}             – Celery task polls for status
"""
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from content_agent.db.session import get_db
from content_agent.integrations.storage.base import StorageBackend, get_storage
from content_agent.models.fill_job import FillJob, FillJobStatus

router = APIRouter(prefix="/fill-jobs", tags=["fill-jobs"])
logger = structlog.get_logger()


# ── Response schemas ─────────────────────────────────────────────────────────

class FillJobResponse(BaseModel):
    id: str
    file_key: str
    frame_id: str
    slide_type: str
    slide_index: int
    text_fills: dict
    image_fills: dict

    model_config = {"from_attributes": True}


class FillJobStatusResponse(BaseModel):
    id: str
    status: FillJobStatus
    result_storage_key: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class ErrorPayload(BaseModel):
    message: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=FillJobResponse | None)
async def claim_pending_job(
    instance_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> FillJob | None:
    """Plugin calls this to claim the next pending job (FIFO)."""
    result = await db.execute(
        select(FillJob)
        .where(FillJob.status == FillJobStatus.PENDING)
        .order_by(FillJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = FillJobStatus.PROCESSING
    job.plugin_instance_id = instance_id
    await db.commit()
    await db.refresh(job)

    logger.info("fill_job.claimed", job_id=str(job.id), slide_type=job.slide_type)
    return job


@router.get("/{job_id}", response_model=FillJobStatusResponse)
async def get_fill_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FillJob:
    """Celery task polls this to know when its fill job is done."""
    result = await db.execute(select(FillJob).where(FillJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="FillJob not found")
    return job


@router.post("/{job_id}/complete", response_model=FillJobStatusResponse)
async def complete_fill_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    storage: Annotated[StorageBackend, Depends(get_storage)] = None,
) -> FillJob:
    """Plugin POSTs the exported PNG (raw bytes, Content-Type: image/png) here."""
    result = await db.execute(select(FillJob).where(FillJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="FillJob not found")
    if job.status not in (FillJobStatus.PROCESSING, FillJobStatus.PENDING):
        raise HTTPException(status_code=409, detail=f"Job already in status {job.status}")

    png_data = await request.body()
    storage_key = f"slides/{job.job_id}/{job.slide_index:02d}_{job.slide_type}.png"
    await storage.upload(storage_key, png_data, content_type="image/png")

    job.result_storage_key = storage_key
    job.status = FillJobStatus.DONE
    await db.commit()
    await db.refresh(job)

    logger.info("fill_job.done", job_id=str(job.id), key=storage_key)
    return job


@router.post("/{job_id}/error", response_model=FillJobStatusResponse)
async def fail_fill_job(
    job_id: uuid.UUID,
    payload: ErrorPayload,
    db: AsyncSession = Depends(get_db),
) -> FillJob:
    """Plugin reports an error for a job."""
    result = await db.execute(select(FillJob).where(FillJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="FillJob not found")

    job.status = FillJobStatus.ERROR
    job.error_message = payload.message
    await db.commit()
    await db.refresh(job)

    logger.error("fill_job.error", job_id=str(job.id), error=payload.message)
    return job
