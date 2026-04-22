"""
Figma template cache.

On first use (or when explicitly synced), templates are downloaded from Figma
and saved as:
    template_cache/{frame_id}_template.png   — the base PNG at scale 2x
    template_cache/{frame_id}_nodes.json     — raw Figma node document

Subsequent renders read from disk — zero Figma API calls.

To refresh:  python scripts/sync_figma_cache.py
"""
from __future__ import annotations

import json
import pathlib

import structlog

logger = structlog.get_logger()

_CACHE_DIR = pathlib.Path(__file__).parent / "template_cache"
_CACHE_DIR.mkdir(exist_ok=True)


# ── Public helpers ─────────────────────────────────────────────────────────────

def is_cached(frame_id: str) -> bool:
    return _png_path(frame_id).exists() and _nodes_path(frame_id).exists()


def load_template_png(frame_id: str) -> bytes:
    return _png_path(frame_id).read_bytes()


def load_frame_nodes(frame_id: str) -> dict:
    return json.loads(_nodes_path(frame_id).read_text(encoding="utf-8"))


def save_template(frame_id: str, png_bytes: bytes, frame_doc: dict) -> None:
    _png_path(frame_id).write_bytes(png_bytes)
    _nodes_path(frame_id).write_text(
        json.dumps(frame_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("figma.cache.saved", frame_id=frame_id, png_bytes=len(png_bytes))


def list_cached_frames() -> list[str]:
    return [p.stem.removesuffix("_template") for p in _CACHE_DIR.glob("*_template.png")]


# ── Path helpers ───────────────────────────────────────────────────────────────

def _png_path(frame_id: str) -> pathlib.Path:
    safe = frame_id.replace(":", "-")
    return _CACHE_DIR / f"{safe}_template.png"


def _nodes_path(frame_id: str) -> pathlib.Path:
    safe = frame_id.replace(":", "-")
    return _CACHE_DIR / f"{safe}_nodes.json"
