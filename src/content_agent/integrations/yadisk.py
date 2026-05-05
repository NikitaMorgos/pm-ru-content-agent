"""
Yandex Disk public folder photo picker.

Given a public folder URL (disk.360.yandex.ru or disk.yandex.ru),
lists photos and returns download URLs grouped by slide purpose:
  - white_bg  : white-background product shots  (Белый фон)
  - interior  : lifestyle / interior shots       (Интерьер)
  - macro     : macro / detail interior shots    (Интерьер_Макро)

Within each group photos are further matched by variant string
(colour name) found in the file/subfolder name.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Literal

import httpx

_API = "https://cloud-api.yandex.net/v1/disk/public/resources"
_SUBFOLDER_KEYWORDS: dict[str, str] = {
    "белый фон": "white_bg",
    "интерьер_макро": "macro",
    "интерьер": "interior",
}

PhotoGroup = Literal["white_bg", "interior", "macro"]

ANGLE_FRONT = re.compile(r"front", re.IGNORECASE)
ANGLE_34    = re.compile(r"_34\b|_34\.", re.IGNORECASE)


@dataclass
class PhotoSet:
    """Photos for a single product variant."""
    white_front: str = ""   # белый фон, вид спереди   → превью-слайд
    white_34: str    = ""   # белый фон, угол 3/4      → слайды размеров/материалов
    interior: list[str] = field(default_factory=list)   # интерьерные
    macro: list[str]    = field(default_factory=list)   # макро-детали

    def main_photo(self) -> str:
        """Best single photo to represent the product."""
        return self.white_front or self.white_34 or (self.interior[0] if self.interior else "")

    def _interior_at(self, idx: int) -> str:
        if len(self.interior) > idx:
            return self.interior[idx]
        return self.interior[0] if self.interior else ""

    def slide_photo(self, slide_type: str, category: str = "chair") -> str:
        """
        Pick the most suitable photo for a given slide type.

        Quality contract for chairs:
        - preview: interior (general 3/4), fallback to neutral
        - dimensions / ergonomics / legs: neutral first
        - upholstery: macro first
        - color palette: alternate interior if available
        """
        st = (slide_type or "").strip().lower()
        cat = (category or "").strip().lower()

        if cat == "chair":
            if st in ("preview", "hero"):
                return self._interior_at(0) or self.white_34 or self.white_front or self.main_photo()
            if st in ("dimensions", "seating_ergonomics", "legs_material"):
                return self.white_34 or self.white_front or self._interior_at(0) or self.main_photo()
            if st in ("upholstery_material", "macro"):
                return (self.macro[0] if self.macro else "") or self._interior_at(0) or self.white_34 or self.main_photo()
            if st == "color_palette":
                return self._interior_at(1) or self._interior_at(0) or self.white_34 or self.main_photo()
            return self._interior_at(0) or self.white_34 or self.white_front or self.main_photo()

        # Table/default strategy
        if st in ("preview", "hero", "design_accent"):
            return self._interior_at(0) or self.white_34 or self.white_front or self.main_photo()
        if st in ("dimensions", "dimensions_folded", "dimensions_open", "legs_material"):
            return self.white_34 or self.white_front or self._interior_at(0) or self.main_photo()
        if st in ("utp_tabletop", "mechanism", "macro"):
            return (self.macro[0] if self.macro else "") or self._interior_at(0) or self.main_photo()
        return self.main_photo()


def _api_list(public_key: str, path: str = "/", limit: int = 100) -> list[dict]:
    """Return items from a Yandex Disk public folder."""
    params = {"public_key": public_key, "path": path, "limit": limit}
    try:
        r = httpx.get(_API, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("_embedded", {}).get("items", [])
    except Exception:
        return []


def _group_name(folder_name: str) -> str | None:
    low = folder_name.lower()
    for kw, group in _SUBFOLDER_KEYWORDS.items():
        if kw in low:
            return group
    return None


def _variant_score(name: str, variant: str) -> int:
    """How well does a filename/folder match the desired variant? Higher = better."""
    if not variant:
        return 1
    name_low    = name.lower()
    variant_low = variant.lower()
    # exact substring match
    if variant_low in name_low:
        return 10
    # partial word match
    words = re.split(r"[\s_\-/]+", variant_low)
    hits  = sum(1 for w in words if w and w in name_low)
    return hits


def _collect_files(public_key: str, path: str, variant: str) -> list[dict]:
    """
    Recursively collect image files under path, filtering by variant if given.
    Returns list of {name, file_url, preview_url} dicts.
    """
    items = _api_list(public_key, path)
    results: list[dict] = []
    for item in items:
        if item["type"] == "file" and item.get("mime_type", "").startswith("image/"):
            score = _variant_score(item["name"], variant)
            if score > 0:
                results.append({
                    "name":        item["name"],
                    "file_url":    item.get("file", ""),
                    "preview_url": item.get("preview", ""),
                    "score":       score,
                })
        elif item["type"] == "dir":
            dir_score = _variant_score(item["name"], variant)
            if not variant or dir_score > 0:
                results.extend(_collect_files(public_key, item["path"], variant))
    return results


def _sort_by_angle(files: list[dict]) -> tuple[str, str]:
    """Return (front_url, angle34_url) for a list of photo dicts."""
    front = ""
    a34   = ""
    for f in sorted(files, key=lambda x: -x["score"]):
        url = f["file_url"] or f["preview_url"]
        if not url:
            continue
        name = f["name"]
        if not front and ANGLE_FRONT.search(name):
            front = url
        if not a34 and ANGLE_34.search(name):
            a34 = url
        if front and a34:
            break
    # fallback: first available
    if not front and not a34 and files:
        url = files[0]["file_url"] or files[0]["preview_url"]
        front = url
    return front, a34


def pick_photos(folder_url: str, variant: str = "") -> PhotoSet:
    """
    Main entry point.  Given a public Yandex Disk folder URL and an optional
    variant/colour name, return a PhotoSet with direct download URLs.
    """
    ps = PhotoSet()
    if not folder_url:
        return ps

    public_key = folder_url  # Yandex API accepts full URL as public_key

    # List root to find top-level subfolders
    root_items = _api_list(public_key, "/")
    if not root_items:
        return ps

    # Map: group → list of files
    group_files: dict[str, list[dict]] = {"white_bg": [], "interior": [], "macro": []}

    for item in root_items:
        if item["type"] != "dir":
            continue
        group = _group_name(item["name"])
        if group is None:
            continue
        files = _collect_files(public_key, item["path"], variant)
        group_files[group].extend(files)

    # If no recognised subfolders, treat root as white_bg
    if not any(group_files.values()):
        root_files = _collect_files(public_key, "/", variant)
        group_files["white_bg"] = root_files

    # white_bg → front + 34°
    ps.white_front, ps.white_34 = _sort_by_angle(group_files["white_bg"])

    # interior
    for f in group_files["interior"]:
        url = f["file_url"] or f["preview_url"]
        if url:
            ps.interior.append(url)

    # macro
    for f in group_files["macro"]:
        url = f["file_url"] or f["preview_url"]
        if url:
            ps.macro.append(url)

    return ps
