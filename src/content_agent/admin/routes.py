"""Admin panel API routes."""
from __future__ import annotations

import asyncio
import json
import pathlib
import re

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

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
    if tz.run_pipeline:
        bg.add_task(_run_pipeline, job.id)
    else:
        update_job(
            job.id,
            state="pending",
            current_step="tz_saved",
            current_step_label="ТЗ сохранено (без рендера)",
            step_index=0,
        )
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


@router.post("/api/jobs/{job_id}/slides")
async def upload_slide(
    job_id: str,
    file: UploadFile = File(...),
    slide_type: str = Form(...),
    slide_index: int = Form(0),
) -> JSONResponse:
    """Receive a rendered PNG from the Figma plugin and attach it to the job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    out_dir = pathlib.Path(__file__).parent.parent.parent.parent / "docs" / "figma_renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _build_output_filename(job, slide_type, slide_index)
    out_path = out_dir / fname
    content = await file.read()
    out_path.write_bytes(content)

    suffix = f"_{slide_type}.png"
    new_urls = [u for u in (job.result_urls or []) if not pathlib.Path(u).name.endswith(suffix)]
    new_urls.append(str(out_path))

    done_required = _count_done_required_slides(job, new_urls)
    expected = _expected_slides(job)
    all_slides_done = done_required >= expected
    update_job(
        job_id,
        result_urls=new_urls,
        state="done" if all_slides_done else "running",
        current_step="fill_template" if not all_slides_done else "done",
        current_step_label="Готово" if all_slides_done else "Рендер в Figma...",
    )
    logger.info(
        "admin.slide.uploaded",
        job_id=job_id,
        slide_type=slide_type,
        bytes=len(content),
        done_required=done_required,
        expected=expected,
    )
    return JSONResponse({
        "path": str(out_path),
        "slide_type": slide_type,
        "done_required": done_required,
        "expected_required": expected,
    })


@router.post("/api/jobs/{job_id}/feedback")
async def add_job_feedback(job_id: str, note: str = Form(...)) -> JSONResponse:
    """Store checkpoint feedback notes from reviewers."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    clean = (note or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Feedback note is empty")
    notes = list(job.feedback_notes or [])
    notes.append(clean)
    update_job(job_id, feedback_notes=notes)
    return JSONResponse({"ok": True, "count": len(notes)})


@router.post("/api/jobs/{job_id}/reset-results")
async def reset_job_results(job_id: str) -> JSONResponse:
    """
    Drop previously attached result URLs (e.g. old Pillow outputs)
    before a fresh Figma render run.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    update_job(
        job_id,
        result_urls=[],
        state="running",
        current_step="fill_template",
        current_step_label="Рендер в Figma...",
    )
    return JSONResponse({"ok": True})


def _expected_slides(job: "AdminJob") -> int:
    """How many slides are expected for this job's category."""
    try:
        registry = _load_template_registry()
        category = getattr(job.tz, "category", "")
        cat = registry.get(category, {})
        return sum(1 for s in cat.get("slides", {}).values() if s.get("required", True))
    except Exception:
        return 4


def _count_done_required_slides(job: "AdminJob", urls: list[str]) -> int:
    """
    Count only required slide types present in current result URLs.
    Ignores legacy Pillow names like *_chair_materials.png.
    """
    try:
        registry = _load_template_registry()
        category = getattr(job.tz, "category", "")
        required = {
            slide_type
            for slide_type, cfg in registry.get(category, {}).get("slides", {}).items()
            if cfg.get("required", True)
        }
        found: set[str] = set()
        for url in urls:
            name = pathlib.Path(url).name
            m = re.search(r"_([a-z_]+)\.png$", name)
            if not m:
                continue
            slide_type = m.group(1)
            if slide_type in required:
                found.add(slide_type)
        return len(found)
    except Exception:
        return 0


@router.get("/api/registry")
async def get_registry() -> JSONResponse:
    """Serve template_registry.json to the Figma plugin."""
    return JSONResponse(_load_template_registry())


@router.get("/api/photo-pick")
async def photo_pick(
    folder_url: str,
    variant: str = "",
    slide_type: str = "preview",
    category: str = "chair",
    max_side: int = 0,
) -> Response:
    """Pick the best product photo from a Yandex Disk folder and proxy the image bytes."""
    import httpx
    from content_agent.integrations.yadisk import pick_photos

    try:
        photos = pick_photos(folder_url, variant)
        best_url = photos.slide_photo(slide_type=slide_type, category=category)
        if not best_url:
            return Response(content=b"", media_type="image/png")
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            r = await client.get(best_url)
            r.raise_for_status()
            content = r.content
            media_type = r.headers.get("content-type", "image/jpeg")
            if max_side and max_side > 0:
                try:
                    import io
                    from PIL import Image

                    img = Image.open(io.BytesIO(content))
                    w, h = img.size
                    if max(w, h) > max_side:
                        ratio = max_side / float(max(w, h))
                        resized = img.resize((int(w * ratio), int(h * ratio)))
                    else:
                        resized = img
                    buf = io.BytesIO()
                    resized.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
                    content = buf.getvalue()
                    media_type = "image/jpeg"
                except Exception as resize_exc:
                    logger.warning("photo_pick.resize_failed", error=str(resize_exc))
            return Response(content=content, media_type=media_type)
    except Exception as exc:
        logger.warning("photo_pick.failed", error=str(exc))
        return Response(content=b"", media_type="image/png")


def _build_output_filename(job: "AdminJob", slide_type: str, slide_index: int) -> str:
    """
    Naming convention:
      <variant_id_or_article>_<index>.png
    Keep slide_type suffix for easier replacement on repeated uploads.
    """
    variant_id = getattr(job.tz, "variant_id", "") or getattr(job.tz, "article", "job")
    safe_variant = "".join(ch for ch in str(variant_id) if ch.isalnum() or ch in ("-", "_")) or "job"
    idx = max(1, int(slide_index or 1))
    return f"{safe_variant}_{idx}_{slide_type}.png"


def _load_template_registry() -> dict:
    registry_path = (
        pathlib.Path(__file__).parent.parent
        / "integrations" / "figma" / "template_registry.json"
    )
    with open(registry_path, encoding="utf-8") as f:
        return json.load(f)


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
    """Render slides: try Figma cache first, fall back to full Pillow renderer with real photos."""
    # ── Try Figma (only if cache is warm — no live API calls) ────────────────
    if manifest.get("figma", {}).get("selected_slides"):
        try:
            from content_agent.integrations.figma.cache import is_cached
            from content_agent.workers.tasks.template import fill_figma_template
            figma_info = manifest.get("figma", {})
            slides_meta = figma_info.get("slides_meta", {})
            selected = figma_info.get("selected_slides", [])
            all_cached = all(
                is_cached(slides_meta[s]["frame_id"])
                for s in selected if s in slides_meta
            )
            if all_cached:
                result = fill_figma_template.apply(args=[manifest])
                updated = result.get()
                paths = updated.get("figma", {}).get("slide_png_paths", [])
                if paths:
                    updated["_slide_paths"] = paths
                    logger.info("fill_template.figma_ok", slides=len(paths))
                    return updated
        except Exception as exc:
            logger.warning("fill_template.figma_failed", error=str(exc))

    # ── Pillow renderer with real Yandex Disk photos ──────────────────────────
    manifest["_slide_paths"] = _render_pillow_slides(manifest)
    return manifest


def _render_pillow_slides(manifest: dict) -> list[str]:
    """Build all slides via Pillow + photos from Yandex Disk."""
    import pathlib
    from content_agent.integrations.yadisk import pick_photos
    from content_agent.integrations.slide_builder import build_slides

    # Reconstruct TZ-style data dict for slide_builder
    product = manifest.get("product", {})
    text_blocks = manifest.get("text_blocks", {})
    meta = manifest.get("meta", {})
    benefits = text_blocks.get("benefits", [])
    dims = text_blocks.get("dimensions", [])

    data: dict = {
        "category":           manifest.get("category", "table"),
        "article":            product.get("sku", ""),
        "brand":              product.get("brand", ""),
        "variant":            meta.get("variant", ""),
        "product_name":       product.get("name", ""),
        "width_cm":           dims[0].replace(" см", "") if len(dims) > 0 else "",
        "height_cm":          dims[1].replace(" см", "") if len(dims) > 1 else "",
        "depth_cm":           dims[2].replace(" см", "") if len(dims) > 2 else "",
        "seat_height_cm":     dims[3].replace(" см", "") if len(dims) > 3 else "",
        "tabletop_material":  text_blocks.get("description", ""),
        "tabletop_finish":    meta.get("color_scheme", ""),
        "legs_material":      meta.get("legs_material", ""),
        "fabric_type":        meta.get("fabric_type", ""),
        "frame_material":     meta.get("frame_material", ""),
        "max_load":           meta.get("max_load", ""),
    }
    for i, utp in enumerate(benefits[:5], 1):
        data[f"utp_{i}"] = utp

    # Photo picking
    folder_url = manifest.get("assets", {}).get("photo_folder_url", "")
    variant = meta.get("variant", "")
    try:
        photos = pick_photos(folder_url, variant)
        logger.info("yadisk.picked", folder=folder_url[:60], variant=variant,
                    front=bool(photos.white_front), interior=len(photos.interior))
    except Exception as exc:
        logger.warning("yadisk.failed", error=str(exc))
        from content_agent.integrations.yadisk import PhotoSet
        photos = PhotoSet()

    # Output dir
    out_dir = pathlib.Path(__file__).parent.parent.parent.parent / "docs" / "rendered_slides"
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = build_slides(data=data, photos=photos, out_dir=out_dir, article=data["article"])
    logger.info("pillow_render.done", slides=len(paths))
    return paths


def _demo_slide_paths(manifest: dict) -> list[str]:
    """Return category-specific demo slides when Figma API is unavailable."""
    import pathlib
    demo_dir = pathlib.Path(__file__).parent.parent.parent.parent / "docs" / "demo_slides"
    category = manifest.get("category", "table")
    article = manifest.get("article", "")

    # Try article-specific slides first
    slide_types = ["preview", "dimensions", "materials", "utp"]
    paths = []
    for stype in slide_types:
        candidate = demo_dir / f"{article}_{category}_{stype}.png"
        if candidate.exists():
            paths.append(str(candidate))

    if paths:
        return paths

    # Fall back to any demo slides for the category
    for stype in slide_types:
        for p in demo_dir.glob(f"*_{category}_{stype}.png"):
            paths.append(str(p))
            break  # one per type

    if paths:
        return paths

    # Last resort: any PNG in demo_slides
    for p in sorted(demo_dir.glob("*.png"))[:4]:
        paths.append(str(p))
    return paths


# ── TZ → manifest conversion ──────────────────────────────────────────────────

def _tz_to_manifest(job: AdminJob) -> dict:
    tz = job.tz
    dims = [f"{tz.width_cm}", f"{tz.height_cm}", f"{tz.depth_cm}"]
    if tz.seat_height_cm:
        dims.append(f"{tz.seat_height_cm}")

    benefits = [u for u in [tz.utp_1, tz.utp_2, tz.utp_3, tz.utp_4, tz.utp_5] if u]

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
            "photo_folder_url": tz.photo_folder_url,
            "main_image_url": "",   # заполняется при разборе папки
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
