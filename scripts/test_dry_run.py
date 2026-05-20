"""
Dry-run validator for a real Yandex Disk folder + real TZ.
Runs end-to-end the *server-side* parts of the pipeline (without invoking
the Figma plugin) and writes a human-readable plan to a file.

Usage:
    python scripts/test_dry_run.py <yandex_folder_url> <variant> [<job_json_path>]

If job_json_path is not given, defaults to the latest job pulled from
the production admin API.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

# Make src importable when run from repo root
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from content_agent.integrations.yadisk import pick_photos, PhotoSet  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "dry_run_report.txt"
REGISTRY_PATH = ROOT / "src" / "content_agent" / "integrations" / "figma" / "template_registry.json"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def fetch_latest_job() -> dict:
    url = "https://pm-ru-content-agent-production.up.railway.app/admin/api/jobs"
    resp = urllib.request.urlopen(url, timeout=20)
    data = json.loads(resp.read().decode("utf-8"))
    return data[0] if data else {}


def build_text_values(tz: dict) -> dict:
    """Mirror of buildTextValues() from plugin_ui.html."""
    def with_cm(v):
        s = str(v) if v not in ("", None) else ""
        return f"{s} см" if s else ""

    return {
        "brand":             tz.get("brand", ""),
        "product_title":     tz.get("product_name", ""),
        "product_type":      tz.get("product_name", ""),
        "dimensions_hwl":    " × ".join(
            f"{v} см" for v in (tz.get("width_cm"), tz.get("depth_cm"), tz.get("height_cm")) if v
        ),
        "width_cm":          with_cm(tz.get("width_cm")),
        "height_cm":         with_cm(tz.get("height_cm")),
        "depth_cm":          with_cm(tz.get("depth_cm")),
        "seat_height_cm":    with_cm(tz.get("seat_height_cm")),
        "max_load":          tz.get("max_load", ""),
        "fabric_type":       tz.get("fabric_type", ""),
        "fabric_name":       tz.get("fabric_type", ""),
        "frame_material":    tz.get("frame_material", ""),
        "legs_material":     tz.get("legs_material", ""),
        "legs_material_text": tz.get("legs_material", ""),
        "tabletop_material": tz.get("tabletop_material", ""),
        "tabletop_finish":   tz.get("tabletop_finish", ""),
        "tabletop_load":     tz.get("tabletop_load", ""),
        "capacity_text":     tz.get("capacity_text", ""),
        "height_adjustment": tz.get("height_adjustment", ""),
        "backrest":          tz.get("backrest", ""),
        "comfort":           tz.get("comfort", ""),
        "seat_height":       with_cm(tz.get("seat_height_cm")),
        "color_range":       tz.get("color_range", ""),
        "space_saving":      tz.get("space_saving", ""),
        "design_accent":     tz.get("design_accent", ""),
        "utp_assembly":      tz.get("utp_1", ""),
        "utp_surface":       tz.get("utp_2", ""),
        "utp_care":          tz.get("utp_3", ""),
        "utp_support":       tz.get("utp_1", ""),
        "utp_construction":  tz.get("utp_2", ""),
        "utp_durability":    tz.get("utp_1", ""),
        "utp_scratch":       tz.get("utp_2", ""),
        "utp_washable":      tz.get("utp_3", ""),
        "utp_feel":          tz.get("utp_3", ""),
        "utp_universal":     tz.get("utp_1", ""),
        "utp_label":         tz.get("utp_2", ""),
        "label":             "Антикоготь",
        "description":       tz.get("utp_1", ""),
    }


def filename_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "filename" in qs:
        return qs["filename"][0]
    return parsed.path.rsplit("/", 1)[-1]


def main() -> None:
    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    out("=" * 80)
    out("DRY-RUN REPORT")
    out("=" * 80)

    job = fetch_latest_job()
    if not job:
        out("[ERROR] No jobs found on Railway")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return

    tz = job["tz"]
    out(f"\nJob ID:        {job['id']}")
    out(f"Article:       {tz.get('article')}")
    out(f"Brand:         {tz.get('brand')}")
    out(f"Product:       {tz.get('product_name')}")
    out(f"Variant:       {tz.get('variant')}")
    out(f"Category:      {tz.get('category')}")
    out(f"Photo folder:  {tz.get('photo_folder_url')}")

    # ────────────────────────────────────────────────────────────
    # L1: Photo picking
    # ────────────────────────────────────────────────────────────
    out("\n" + "─" * 80)
    out("L1 — PHOTO PICKER")
    out("─" * 80)

    folder = tz.get("photo_folder_url", "")
    variant = tz.get("variant", "")
    photos: PhotoSet = pick_photos(folder, variant)

    out(f"\nFound photos:")
    out(f"  white_front : {filename_from_url(photos.white_front) or '(none)'}")
    out(f"  white_34    : {filename_from_url(photos.white_34) or '(none)'}")
    out(f"  white_side  : {filename_from_url(photos.white_side) or '(none)'}")
    out(f"  interior    : {len(photos.interior)} files")
    for i, u in enumerate(photos.interior):
        out(f"      [{i}] {filename_from_url(u)}")
    out(f"  macro       : {len(photos.macro)} files")
    for i, u in enumerate(photos.macro):
        out(f"      [{i}] {filename_from_url(u)}")

    registry = load_registry()
    cat_cfg = registry.get(tz.get("category"), {})
    slides = cat_cfg.get("slides", {})

    out(f"\nPhoto chosen per slide:")
    out(f"  {'slide_type':<25} {'photo file':<60}")
    out(f"  {'-' * 25} {'-' * 60}")
    for slide_type, cfg in slides.items():
        if not cfg.get("required"):
            continue
        url = photos.slide_photo(slide_type=slide_type, category=tz.get("category"))
        name = filename_from_url(url) or "(NONE)"
        marker = "  " if url else "❌"
        out(f"  {marker}{slide_type:<23} {name}")

    # ────────────────────────────────────────────────────────────
    # L2: Text mapping
    # ────────────────────────────────────────────────────────────
    out("\n" + "─" * 80)
    out("L2 — TEXT MAPPING (TZ → fill_map values)")
    out("─" * 80)

    text_values = build_text_values(tz)

    for slide_type, cfg in slides.items():
        if not cfg.get("required"):
            continue
        out(f"\n  ▸ {slide_type} (frame {cfg.get('frame_id')})")
        fill_map = cfg.get("fill_map", {})
        if not fill_map:
            out(f"      (empty fill_map)")
            continue
        for field, node_id in fill_map.items():
            v = text_values.get(field, "")
            mark = "✓" if v else "✗ EMPTY"
            out(f"      {mark}  node {node_id:<10} field={field:<22} value={v!r}")

    # ────────────────────────────────────────────────────────────
    # Summary of gaps
    # ────────────────────────────────────────────────────────────
    out("\n" + "─" * 80)
    out("GAPS — fields referenced in fill_map but empty in TZ")
    out("─" * 80)
    gaps: dict[str, list[str]] = {}
    for slide_type, cfg in slides.items():
        if not cfg.get("required"):
            continue
        for field in cfg.get("fill_map", {}):
            v = text_values.get(field, "")
            if not v:
                gaps.setdefault(slide_type, []).append(field)
    if not gaps:
        out("  (no gaps — all referenced fields populated)")
    else:
        for slide_type, fields in gaps.items():
            out(f"  {slide_type}: {', '.join(fields)}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    out(f"\n[Report written to {OUT}]")


if __name__ == "__main__":
    main()
