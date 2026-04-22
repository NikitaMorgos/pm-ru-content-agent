"""
Sync Figma templates to local cache.

Run ONCE (or when Figma designs change) to download all template PNGs
and node JSON into the local cache. After that, the pipeline renders
slides offline — no API calls per job.

Usage:
    python scripts/sync_figma_cache.py
    python scripts/sync_figma_cache.py --force   # re-download even if cached
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import pathlib

# Add src to path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from content_agent.config import settings
from content_agent.integrations.figma.client import FigmaClient
from content_agent.integrations.figma.cache import is_cached, save_template, list_cached_frames

REGISTRY_PATH = (
    pathlib.Path(__file__).parent.parent
    / "src" / "content_agent" / "integrations" / "figma" / "template_registry.json"
)


def main(force: bool = False) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    file_key: str = registry["_meta"]["figma_file_key"]

    token = settings.figma_access_token.get_secret_value()
    client = FigmaClient(token=token)

    # Collect all unique frame IDs across all categories
    frames_to_sync: list[tuple[str, str, str]] = []  # (category, slide_type, frame_id)
    for cat_key, cat_val in registry.items():
        if cat_key.startswith("_"):
            continue
        slides = cat_val.get("slides", {})
        for slide_type, slide_cfg in slides.items():
            frame_id = slide_cfg["frame_id"]
            frames_to_sync.append((cat_key, slide_type, frame_id))

    # De-duplicate by frame_id (same frame might appear in multiple categories)
    seen: set[str] = set()
    unique_frames = []
    for cat, slide, fid in frames_to_sync:
        if fid not in seen:
            seen.add(fid)
            unique_frames.append((cat, slide, fid))

    total = len(unique_frames)
    print(f"\nFigma template cache sync")
    print(f"  File key : {file_key}")
    print(f"  Frames   : {total} unique frames")
    print(f"  Already cached: {len(list_cached_frames())}")
    print()

    downloaded = 0
    skipped = 0
    errors = 0

    for i, (cat, slide_type, frame_id) in enumerate(unique_frames):
        if not force and is_cached(frame_id):
            print(f"  [{i+1}/{total}] SKIP  {cat}/{slide_type} ({frame_id}) — already cached")
            skipped += 1
            continue

        print(f"  [{i+1}/{total}] SYNC  {cat}/{slide_type} ({frame_id})...", end="", flush=True)
        try:
            if downloaded > 0:
                time.sleep(2.5)  # respect rate limit
            png_bytes = client.export_frame_png(file_key, frame_id, scale=2.0)
            frame_doc = client.get_frame_node(file_key, frame_id)
            save_template(frame_id, png_bytes, frame_doc)
            print(f" OK ({len(png_bytes)//1024} KB)")
            downloaded += 1
        except Exception as exc:
            print(f" ERROR: {exc}")
            errors += 1

    print()
    print(f"Done. Downloaded: {downloaded}  Skipped: {skipped}  Errors: {errors}")
    if errors:
        print("  Tip: Re-run after a few minutes if you hit 429 rate limits.")
    else:
        print("  All templates cached. Pipeline will now render offline.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Figma templates to local cache")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    args = parser.parse_args()
    main(force=args.force)
