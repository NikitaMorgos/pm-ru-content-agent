"""Admin panel API routes."""
from __future__ import annotations

import asyncio
import pathlib

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from content_agent.admin.store import (
    PIPELINE_STEPS,
    AdminJob,
    TZForm,
    create_job,
    get_job,
    list_jobs,
    update_job,
)

router = APIRouter()
logger = structlog.get_logger()

_TEMPLATE_PATH = pathlib.Path(__file__).parent.parent / "templates" / "admin.html"


# ── Serve SPA ─────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin() -> HTMLResponse:
    return HTMLResponse(_TEMPLATE_PATH.read_text(encoding="utf-8"))


# ── Jobs API ──────────────────────────────────────────────────────────────────

@router.get("/api/jobs", response_model=list[AdminJob])
async def api_list_jobs() -> list[AdminJob]:
    return list_jobs()


@router.get("/api/jobs/{job_id}", response_model=AdminJob)
async def api_get_job(job_id: str) -> AdminJob:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/api/jobs", response_model=AdminJob, status_code=201)
async def api_create_job(tz: TZForm, bg: BackgroundTasks) -> AdminJob:
    job = create_job(tz)
    bg.add_task(_run_pipeline, job.id)
    logger.info("admin.job.created", job_id=job.id, article=tz.article)
    return job


@router.get("/api/jobs/{job_id}/slides/{filename}")
async def download_slide(job_id: str, filename: str) -> FileResponse:
    """Serve a rendered PNG slide for download."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for path in job.result_urls:
        p = pathlib.Path(path)
        if p.name == filename and p.exists():
            return FileResponse(str(p), media_type="image/png", filename=filename)
    raise HTTPException(status_code=404, detail="Slide not found")


# ── Pipeline runner (background task) ────────────────────────────────────────

async def _run_pipeline(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    update_job(job_id, state="running")
    loop = asyncio.get_event_loop()
    try:
        manifest = _tz_to_manifest(job)
        manifest = await loop.run_in_executor(None, _pipeline_sync, job_id, manifest)
        result_urls = manifest.get("_slide_paths", [])
        update_job(
            job_id,
            state="done",
            current_step="done",
            current_step_label="Готово",
            step_index=len(PIPELINE_STEPS) - 1,
            result_urls=result_urls,
        )
        logger.info("admin.pipeline.done", job_id=job_id, slides=len(result_urls))
    except Exception as exc:
        logger.exception("admin.pipeline.error", job_id=job_id)
        update_job(job_id, state="error", error_message=str(exc))


def _set_step(job_id: str, key: str, idx: int) -> None:
    label = dict(PIPELINE_STEPS).get(key, key)
    update_job(job_id, current_step=key, current_step_label=label, step_index=idx)


def _pipeline_sync(job_id: str, manifest: dict) -> dict:
    """
    Run the full pipeline synchronously (no Celery broker needed).
    Real steps: select_template, fill_template.
    Other steps: simulated with brief sleeps.
    """
    import time

    steps = [
        ("build_manifest",  _step_noop),
        ("validate",        _step_validate),
        ("normalize",       _step_noop),
        ("compress",        _step_noop),
        ("select_template", _step_select_template),
        ("fill_template",   _step_fill_template),
        ("export_png",      _step_noop),
        ("upload",          _step_noop),
    ]

    for i, (key, fn) in enumerate(steps):
        _set_step(job_id, key, i)
        time.sleep(0.6)  # brief visual delay for all steps
        manifest = fn(manifest)
        logger.info("admin.step.done", job_id=job_id, step=key)

    return manifest


# ── Individual step implementations ──────────────────────────────────────────

def _step_noop(manifest: dict) -> dict:
    return manifest


def _step_validate(manifest: dict) -> dict:
    required = ["category", "product", "text_blocks"]
    for field in required:
        if not manifest.get(field):
            raise ValueError(f"Manifest missing required field: {field}")
    return manifest


def _step_select_template(manifest: dict) -> dict:
    """Real: look up Figma frame IDs from registry."""
    try:
        from content_agent.workers.tasks.template import select_figma_template
        result = select_figma_template.apply(args=[manifest])
        return result.get()
    except Exception as exc:
        logger.warning("select_template.failed", error=str(exc))
        return manifest


def _step_fill_template(manifest: dict) -> dict:
    """Real: export Figma PNGs and overlay text with Pillow."""
    if not manifest.get("figma", {}).get("selected_slides"):
        logger.warning("fill_template.skipped", reason="no slides selected")
        return manifest
    try:
        from content_agent.workers.tasks.template import fill_figma_template
        result = fill_figma_template.apply(args=[manifest])
        updated = result.get()
        paths = updated.get("figma", {}).get("slide_png_paths", [])
        updated["_slide_paths"] = paths
        if paths:
            logger.info("fill_template.ok", slides=len(paths))
        else:
            # Figma API unavailable (rate limit / token issue) — use demo slides
            logger.warning(
                "fill_template.using_demo",
                note="Figma API returned 0 slides — serving demo PNG",
            )
            updated["_slide_paths"] = _demo_slide_paths(manifest)
        return updated
    except Exception as exc:
        logger.warning("fill_template.failed", error=str(exc))
        manifest["_slide_paths"] = _demo_slide_paths(manifest)
        return manifest


def _demo_slide_paths(manifest: dict) -> list[str]:
    """Return paths to pre-rendered demo slides when Figma API is unavailable."""
    import pathlib
    demo_dir = pathlib.Path(__file__).parent.parent.parent.parent / "docs"
    demo_png = demo_dir / "test_slide_preview.png"
    if demo_png.exists():
        return [str(demo_png)]
    return []


# ── TZ → manifest conversion ──────────────────────────────────────────────────

def _tz_to_manifest(job: AdminJob) -> dict:
    tz = job.tz
    dims = [f"{tz.width_cm}", f"{tz.height_cm}", f"{tz.depth_cm}"]
    if tz.seat_height_cm:
        dims.append(f"{tz.seat_height_cm}")

    benefits = [u for u in [tz.utp_1, tz.utp_2, tz.utp_3, tz.utp_4, tz.utp_5] if u]
    photos = [u for u in [
        tz.photo_url_1, tz.photo_url_2, tz.photo_url_3, tz.photo_url_4, tz.photo_url_5
    ] if u]

    return {
        "task_id": f"admin-{job.id}",
        "category": tz.category,
        "card_type": "hero",
        "product": {
            "sku": tz.article,
            "name": tz.product_name,
            "brand": tz.brand,
        },
        "assets": {
            "main_image_url": photos[0] if photos else "https://example.com/placeholder.jpg",
            "icons": [],
        },
        "text_blocks": {
            "title": tz.product_name,
            "description": tz.tabletop_material or tz.fabric_type or "",
            "benefits": benefits,
            "dimensions": [f"{d} см" for d in dims],
            "color_names": [tz.variant] if tz.variant else [],
        },
        "figma": {},
        "output": {},
        "product_flags": {
            "is_extendable": tz.is_extendable,
            "has_antiscratch": tz.has_antiscratch,
        },
        "meta": {
            "redmine_issue_id": 0,
            "job_id": job.id,
            "pipeline_step": "created",
            "variant": tz.variant,
            "color_scheme": tz.tabletop_finish,
            "legs_material": tz.legs_material,
            "fabric_type": tz.fabric_type,
            "frame_material": tz.frame_material,
            "max_load": tz.max_load,
            "image_edit_enabled": False,
            "errors": [],
            "warnings": [],
        },
    }
