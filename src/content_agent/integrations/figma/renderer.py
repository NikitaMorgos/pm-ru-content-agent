"""
Pillow-based slide renderer.

Flow for each slide:
  1.  Export the Figma template frame as PNG  (background + placeholder text baked in)
  2.  For each text field in fill_map:
        a. Get absoluteBoundingBox from Figma node data
        b. Convert to pixel coords  (subtract frame origin, multiply by export scale)
        c. Sample the dominant background colour from that region
        d. Erase old text: paint a solid rect with the sampled colour
        e. Draw new text: font / size / weight / alignment from Figma style
  3.  Return the resulting PNG bytes
"""
from __future__ import annotations

import io
import pathlib
from dataclasses import dataclass, field
from typing import Any

import structlog
from PIL import Image, ImageDraw, ImageFont

logger = structlog.get_logger()

# ── Font resolution ───────────────────────────────────────────────────────────

_FONTS_DIR = pathlib.Path(__file__).parent / "fonts"
_SYSTEM_FONTS = pathlib.Path("C:/Windows/Fonts")

_WEIGHT_MAP: dict[int, list[str]] = {
    # weight → candidate filenames in order of preference
    100: ["segoeuil.ttf", "calibril.ttf", "arialn.ttf"],
    200: ["segoeuil.ttf", "calibril.ttf", "arialn.ttf"],
    300: ["segoeuil.ttf", "calibril.ttf", "arialn.ttf"],
    400: ["segoeui.ttf",  "calibri.ttf",  "arial.ttf"],
    500: ["segoeui.ttf",  "calibri.ttf",  "arial.ttf"],
    600: ["segoeuib.ttf", "calibrib.ttf", "arialbd.ttf"],
    700: ["segoeuib.ttf", "calibrib.ttf", "arialbd.ttf"],
    800: ["segoeuib.ttf", "calibrib.ttf", "arialbd.ttf"],
    900: ["segoeuib.ttf", "calibrib.ttf", "arialbd.ttf"],
}


def _resolve_font(font_size: float, font_weight: int = 400) -> ImageFont.FreeTypeFont:
    """Return an ImageFont for the given size and weight, falling back gracefully."""
    candidates = _WEIGHT_MAP.get(font_weight, _WEIGHT_MAP[400])
    for fname in candidates:
        # Check project fonts dir first, then system
        for base in (_FONTS_DIR, _SYSTEM_FONTS):
            path = base / fname
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=int(font_size))
                except Exception:
                    continue
    logger.warning("font.fallback", size=font_size, weight=font_weight)
    return ImageFont.load_default(size=int(font_size))


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TextLayerInfo:
    """Everything Pillow needs to erase + redraw one text layer."""
    node_id: str
    field_name: str
    # Pixel coordinates in the exported PNG (already scaled)
    px: int
    py: int
    pw: int
    ph: int
    # Figma style
    font_family: str
    font_size: float
    font_weight: int
    text_align: str          # LEFT | CENTER | RIGHT
    fill_rgba: tuple[int, int, int, int]   # text colour
    placeholder_text: str


# ── Node traversal helpers ────────────────────────────────────────────────────

def _find_node_by_id(node: dict, target_id: str) -> dict | None:
    if node.get("id") == target_id:
        return node
    for child in node.get("children", []):
        found = _find_node_by_id(child, target_id)
        if found:
            return found
    return None


def _rgba_from_figma(color: dict[str, float]) -> tuple[int, int, int, int]:
    return (
        int(color.get("r", 0) * 255),
        int(color.get("g", 0) * 255),
        int(color.get("b", 0) * 255),
        int(color.get("a", 1) * 255),
    )


# ── Core: extract TextLayerInfo from Figma node data ─────────────────────────

def extract_text_layers(
    frame_doc: dict,
    fill_map: dict[str, str],          # {field_name: node_id}
    frame_abs_x: float,
    frame_abs_y: float,
    export_scale: float = 2.0,
) -> dict[str, TextLayerInfo]:
    """
    Walk the frame document and collect TextLayerInfo for every node_id
    that appears in fill_map.
    """
    result: dict[str, TextLayerInfo] = {}
    node_id_to_field = {v: k for k, v in fill_map.items()}

    for node_id, field_name in node_id_to_field.items():
        node = _find_node_by_id(frame_doc, node_id)
        if node is None or node.get("type") != "TEXT":
            logger.warning("renderer.node_not_found", node_id=node_id, field=field_name)
            continue

        bbox = node.get("absoluteBoundingBox", {})
        style = node.get("style", {})
        fills = node.get("fills", [])

        # Convert Figma canvas coords → frame-relative pixel coords
        rel_x = (bbox.get("x", 0) - frame_abs_x) * export_scale
        rel_y = (bbox.get("y", 0) - frame_abs_y) * export_scale
        rel_w = bbox.get("width", 200) * export_scale
        rel_h = bbox.get("height", 50) * export_scale

        # Text fill colour (first solid fill, default white)
        text_color: tuple[int, int, int, int] = (255, 255, 255, 255)
        for f in fills:
            if f.get("type") == "SOLID" and f.get("visible", True) is not False:
                text_color = _rgba_from_figma(f["color"])
                break

        result[field_name] = TextLayerInfo(
            node_id=node_id,
            field_name=field_name,
            px=int(rel_x),
            py=int(rel_y),
            pw=int(rel_w),
            ph=int(rel_h),
            font_family=style.get("fontFamily", "Segoe UI"),
            font_size=style.get("fontSize", 24) * export_scale,
            font_weight=style.get("fontWeight", 400),
            text_align=style.get("textAlignHorizontal", "LEFT"),
            fill_rgba=text_color,
            placeholder_text=node.get("characters", ""),
        )

    return result


# ── Background sampling ───────────────────────────────────────────────────────

def _sample_border_color(
    img: Image.Image,
    px: int,
    py: int,
    pw: int,
    ph: int,
    border: int = 6,
) -> tuple[int, int, int]:
    """
    Sample the background colour from a thin border AROUND the text bbox
    (not from inside where the old placeholder text is).
    This gives a cleaner background estimate, especially over photos.
    """
    W, H = img.size
    pixels: list[tuple[int, int, int]] = []

    # Top strip
    for x in range(max(0, px - border), min(W, px + pw + border)):
        for y in range(max(0, py - border), max(0, py)):
            pixels.append(img.getpixel((x, y))[:3])  # type: ignore[misc]
    # Bottom strip
    for x in range(max(0, px - border), min(W, px + pw + border)):
        for y in range(min(H, py + ph), min(H, py + ph + border)):
            pixels.append(img.getpixel((x, y))[:3])  # type: ignore[misc]
    # Left strip
    for x in range(max(0, px - border), max(0, px)):
        for y in range(max(0, py), min(H, py + ph)):
            pixels.append(img.getpixel((x, y))[:3])  # type: ignore[misc]
    # Right strip
    for x in range(min(W, px + pw), min(W, px + pw + border)):
        for y in range(max(0, py), min(H, py + ph)):
            pixels.append(img.getpixel((x, y))[:3])  # type: ignore[misc]

    if not pixels:
        return _sample_background_color(img, px, py, pw, ph)

    n = len(pixels)
    r = sum(p[0] for p in pixels) // n
    g = sum(p[1] for p in pixels) // n
    b = sum(p[2] for p in pixels) // n
    return (r, g, b)


def _sample_background_color(
    img: Image.Image,
    px: int,
    py: int,
    pw: int,
    ph: int,
    padding: int = 4,
) -> tuple[int, int, int]:
    """
    Sample the dominant colour from a slightly-padded region of the image.
    Used to 'erase' placeholder text by painting the background colour.
    """
    W, H = img.size
    # Expand the sampling area slightly to capture the region behind the text
    x0 = max(0, px - padding)
    y0 = max(0, py - padding)
    x1 = min(W, px + pw + padding)
    y1 = min(H, py + ph + padding)

    if x0 >= x1 or y0 >= y1:
        return (255, 255, 255)

    region = img.crop((x0, y0, x1, y1)).convert("RGB")
    # Compute average colour of the region
    pixels = list(region.getdata())
    n = len(pixels)
    if n == 0:
        return (255, 255, 255)
    r = sum(p[0] for p in pixels) // n
    g = sum(p[1] for p in pixels) // n
    b = sum(p[2] for p in pixels) // n
    return (r, g, b)


# ── Main render function ──────────────────────────────────────────────────────

def render_slide(
    template_png_bytes: bytes,
    text_layers: dict[str, TextLayerInfo],
    text_values: dict[str, str],         # {field_name: actual_value}
) -> bytes:
    """
    Take the exported template PNG and replace each text field
    with the actual value from text_values.

    Returns PNG bytes of the final slide.
    """
    img = Image.open(io.BytesIO(template_png_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for field_name, layer in text_layers.items():
        new_text = text_values.get(field_name, "").strip()
        if not new_text:
            continue  # nothing to render — leave placeholder as is

        px, py, pw, ph = layer.px, layer.py, layer.pw, layer.ph

        # 1. Sample background and erase old text.
        # Sample from a 2-pixel-wide border AROUND the bbox (not from inside where
        # the old text lives) so we get the true background colour.
        bg_rgb = _sample_border_color(img, px, py, pw, ph, border=6)
        margin = max(4, int(layer.font_size * 0.12))
        draw.rectangle(
            [px - margin, py - margin, px + pw + margin, py + ph + margin],
            fill=(*bg_rgb, 255),
        )

        # 2. Choose font — auto-reduce size until text fits on one line if possible
        font_size = layer.font_size
        font = _resolve_font(font_size, layer.font_weight)
        # Auto-shrink: reduce size by 10% steps until single-line text fits in bbox width
        for _ in range(6):
            test_bbox = draw.textbbox((0, 0), new_text, font=font)
            if test_bbox[2] - test_bbox[0] <= pw:
                break
            font_size *= 0.88
            font = _resolve_font(font_size, layer.font_weight)

        # 3. Draw text
        text_color = layer.fill_rgba
        align = layer.text_align.lower()
        _draw_text_wrapped(draw, new_text, font, text_color, px, py, pw, ph, align)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _draw_text_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int, int],
    x: int,
    y: int,
    max_w: int,
    max_h: int,
    align: str = "left",
) -> None:
    """Draw text wrapping at word boundaries to fit within max_w × max_h."""
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    # Measure line height
    sample_bbox = draw.textbbox((0, 0), "Ay", font=font)
    line_h = sample_bbox[3] - sample_bbox[1]
    line_spacing = int(line_h * 1.15)

    # Vertical centering
    total_h = len(lines) * line_spacing
    cur_y = y + max(0, (max_h - total_h) // 2)

    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_w = line_bbox[2] - line_bbox[0]

        if align == "center":
            cur_x = x + (max_w - line_w) // 2
        elif align == "right":
            cur_x = x + max_w - line_w
        else:
            cur_x = x

        draw.text((cur_x, cur_y), line, font=font, fill=color)
        cur_y += line_spacing
