"""select_figma_template + fill_figma_template Celery tasks (Python/Pillow renderer)."""
from __future__ import annotations

import json
import pathlib
import tempfile

import structlog

from content_agent.workers.celery_app import celery_app

logger = structlog.get_logger()

REGISTRY_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "integrations" / "figma" / "template_registry.json"
)


def _load_registry() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── select_figma_template ─────────────────────────────────────────────────────

@celery_app.task(bind=True, name="content_agent.workers.tasks.template.select_figma_template")
def select_figma_template(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Map product category → Figma frame_ids for each required slide."""
    log = logger.bind(task_id=manifest_dict.get("task_id"))
    log.info("template.select.start")

    registry = _load_registry()
    category = _detect_category(manifest_dict)
    cat_registry = registry.get(category)
    if not cat_registry:
        raise ValueError(f"Unknown category '{category}' — not in template_registry.json")

    file_key = registry["_meta"]["figma_file_key"]
    slides_meta = cat_registry["slides"]
    product_flags = manifest_dict.get("product_flags", {})

    selected_slides = [
        slide_type
        for slide_type, cfg in slides_meta.items()
        if cfg.get("required", True)
        or (cfg.get("condition_field") and product_flags.get(cfg["condition_field"]))
    ]

    manifest_dict["figma"] = manifest_dict.get("figma", {})
    manifest_dict["figma"].update({
        "file_key": file_key,
        "category": category,
        "selected_slides": selected_slides,
        "slides_meta": slides_meta,
    })
    manifest_dict["meta"]["pipeline_step"] = "select_figma_template"

    log.info("template.select.done", category=category, slides=selected_slides)
    return manifest_dict


def _detect_category(manifest_dict: dict) -> str:
    explicit = manifest_dict.get("category") or manifest_dict.get("meta", {}).get("category")
    if explicit:
        return explicit
    name = (manifest_dict.get("product", {}).get("name", "") or "").lower()
    if "стол" in name or "table" in name:
        return "table"
    if "стул" in name or "chair" in name:
        return "chair"
    raise ValueError("Cannot detect category — set manifest.category explicitly")


# ── fill_figma_template ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="content_agent.workers.tasks.template.fill_figma_template",
    max_retries=3,
    default_retry_delay=10,
)
def fill_figma_template(self, manifest_dict: dict) -> dict:  # type: ignore[override]
    """Render each slide using cached Figma templates (no API calls if cache is warm)."""
    import time
    from content_agent.config import settings
    from content_agent.integrations.figma.cache import (
        is_cached, load_template_png, load_frame_nodes, save_template,
    )
    from content_agent.integrations.figma.client import FigmaClient
    from content_agent.integrations.figma.renderer import extract_text_layers, render_slide

    log = logger.bind(task_id=manifest_dict.get("task_id"))
    log.info("template.fill.start")

    figma_info = manifest_dict.get("figma", {})
    file_key: str = figma_info["file_key"]
    selected_slides: list[str] = figma_info["selected_slides"]
    slides_meta: dict = figma_info["slides_meta"]

    client: FigmaClient | None = None
    api_calls = 0

    def _get_client() -> FigmaClient:
        nonlocal client
        if client is None:
            client = FigmaClient(token=settings.figma_access_token.get_secret_value())
        return client

    text_values = _build_text_values(manifest_dict)
    slide_png_paths: list[str] = []

    for index, slide_type in enumerate(selected_slides):
        slide_cfg = slides_meta[slide_type]
        frame_id: str = slide_cfg["frame_id"]
        fill_map: dict[str, str] = slide_cfg.get("fill_map", {})
        log.info("template.fill.slide", slide_type=slide_type, frame_id=frame_id)

        try:
            # ── Step 1: Get template PNG ──────────────────────────────────────
            if is_cached(frame_id):
                png_bytes = load_template_png(frame_id)
                frame_doc = load_frame_nodes(frame_id)
                log.info("template.fill.cache_hit", frame_id=frame_id)
            else:
                log.info("template.fill.cache_miss", frame_id=frame_id)
                if api_calls > 0:
                    time.sleep(2.0)  # respect rate limit
                cl = _get_client()
                png_bytes = cl.export_frame_png(file_key, frame_id, scale=2.0)
                frame_doc = cl.get_frame_node(file_key, frame_id)
                api_calls += 2
                # Persist to cache for future renders
                save_template(frame_id, png_bytes, frame_doc)

            # ── Step 2: Extract text layer bounds ─────────────────────────────
            frame_bbox = frame_doc.get("absoluteBoundingBox", {})
            frame_x = frame_bbox.get("x", 0)
            frame_y = frame_bbox.get("y", 0)
            text_layers = extract_text_layers(
                frame_doc=frame_doc,
                fill_map=fill_map,
                frame_abs_x=frame_x,
                frame_abs_y=frame_y,
                export_scale=2.0,
            )

            # ── Step 3: Render ────────────────────────────────────────────────
            result_png = render_slide(
                template_png_bytes=png_bytes,
                text_layers=text_layers,
                text_values=text_values,
            )

            tmp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".png",
                prefix=f"slide_{index:02d}_{slide_type}_",
            )
            tmp.write(result_png)
            tmp.close()
            slide_png_paths.append(tmp.name)
            log.info("template.fill.slide_done", path=tmp.name, bytes=len(result_png))

        except Exception as exc:
            log.warning(
                "template.fill.slide_error",
                slide_type=slide_type,
                error=str(exc),
                rendered_so_far=len(slide_png_paths),
            )

    manifest_dict["figma"]["slide_png_paths"] = slide_png_paths
    manifest_dict["meta"]["pipeline_step"] = "fill_figma_template"
    log.info("template.fill.done", slides=len(slide_png_paths), api_calls=api_calls)
    return manifest_dict


def _build_text_values(manifest_dict: dict) -> dict[str, str]:
    """Flatten manifest into {field_name: text} for renderer."""
    product = manifest_dict.get("product", {})
    text_blocks = manifest_dict.get("text_blocks", {})
    meta = manifest_dict.get("meta", {})
    dims = text_blocks.get("dimensions", [])
    benefits = text_blocks.get("benefits", [])

    def _benefit(i: int) -> str:
        return benefits[i] if i < len(benefits) else ""

    def _dim(i: int) -> str:
        return dims[i] if i < len(dims) else ""

    return {
        "brand":              product.get("brand", ""),
        "product_type":       product.get("name", ""),
        "product_title":      product.get("name", ""),
        "dimensions_hwl":     " × ".join(dims[:3]) if dims else "",
        "width_cm":           _dim(0),
        "height_cm":          _dim(1),
        "depth_cm":           _dim(2),
        "seat_height_cm":     _dim(3),
        "max_load":           meta.get("max_load", ""),
        "utp_assembly":       _benefit(0),
        "utp_surface":        _benefit(1),
        "utp_care":           _benefit(2),
        "utp_support":        _benefit(3),
        "utp_construction":   _benefit(4),
        "utp_durability":     _benefit(5),
        "utp_scratch":        _benefit(6),
        "utp_washable":       _benefit(7),
        "utp_feel":           _benefit(8),
        "utp_universal":      _benefit(9),
        "fabric_type":        meta.get("fabric_type", ""),
        "tabletop_finish":    meta.get("color_scheme", ""),
        "tabletop_material":  text_blocks.get("description", ""),
        "tabletop_load":      meta.get("tabletop_load", ""),
        "legs_material":      meta.get("legs_material", ""),
        "legs_material_text": meta.get("legs_material", ""),
        "height_adjustment":  meta.get("height_adjustment", ""),
        "capacity_text":      meta.get("capacity_text", ""),
        "backrest":           meta.get("backrest", ""),
        "comfort":            meta.get("comfort", ""),
        "seat_height":        meta.get("seat_height_text", ""),
        "color_range":        meta.get("color_range", ""),
        "space_saving":       meta.get("space_saving", ""),
        "design_accent":      meta.get("design_accent", ""),
        "color_palette":      ", ".join(text_blocks.get("color_names", [])),
        "label":              meta.get("antiscratch_label", "Антикоготь"),
        "description":        text_blocks.get("description", ""),
    }
