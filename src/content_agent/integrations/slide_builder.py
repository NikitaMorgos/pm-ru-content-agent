"""
Pillow-based slide builder.

Renders product card slides (1000×1000 px) using real product photos
downloaded from Yandex Disk (or any direct URL).

Slide types:
  preview     — hero shot: large product photo + title + dimensions
  dimensions  — table with all dimensions + diagram placeholder
  materials   — materials table  (table: tabletop/legs, chair: fabric/frame)
  utp         — numbered benefits list
"""
from __future__ import annotations

import io
import pathlib
import textwrap
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

# ── Constants ─────────────────────────────────────────────────────────────────

W = H = 1000          # output canvas
PADDING = 48
ACCENT_HEIGHT = 8
FOOTER_H = 64
HEADER_H = 72
PHOTO_MARGIN = 16

# Colour palettes per category
PALETTES = {
    "table": {
        "accent":   (30,  60, 120),
        "accent_lt":(210, 220, 240),
        "bg":       (245, 245, 240),
        "text":     (20,  20,  20),
        "muted":    (100, 100, 100),
        "row_even": (235, 237, 243),
    },
    "chair": {
        "accent":   (75,  35, 100),
        "accent_lt":(225, 210, 235),
        "bg":       (248, 246, 250),
        "text":     (20,  20,  20),
        "muted":    (100, 100, 100),
        "row_even": (237, 230, 243),
    },
}

# Windows fonts
_FONT_REGULAR = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
_FONT_BOLD    = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "C:/Windows/Fonts/Arial.ttf"]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in candidates:
        if pathlib.Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _download_image(url: str) -> Image.Image | None:
    """Download an image from URL; return PIL Image or None on failure."""
    if not url:
        return None
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def _paste_photo(
    canvas: Image.Image,
    photo: Image.Image | None,
    box: tuple[int, int, int, int],
    placeholder_text: str = "[ Фото товара ]",
) -> None:
    """Paste photo into box (x1,y1,x2,y2) with aspect-ratio fit, or draw placeholder."""
    draw = ImageDraw.Draw(canvas)
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1

    if photo is None:
        # Placeholder
        draw.rectangle([x1, y1, x2, y2], fill=(215, 215, 210), outline=(185, 185, 180), width=1)
        f = _font(_FONT_REGULAR, 22)
        draw.text(((x1+x2)//2, (y1+y2)//2), placeholder_text, font=f, fill=(160,160,155), anchor="mm")
        return

    # Aspect-ratio fit (cover)
    iw, ih = photo.size
    scale = max(bw / iw, bh / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    photo_resized = photo.resize((nw, nh), Image.LANCZOS)
    ox = (nw - bw) // 2
    oy = (nh - bh) // 2
    cropped = photo_resized.crop((ox, oy, ox + bw, oy + bh))
    canvas.paste(cropped, (x1, y1))


def _draw_header(draw: ImageDraw.ImageDraw, data: dict, palette: dict, slide_label: str) -> None:
    """Draw top accent bar, category tag, brand+article, slide type label."""
    draw.rectangle([(0, 0), (W, ACCENT_HEIGHT)], fill=palette["accent"])

    # Category tag
    cat_text = "СТОЛ" if data.get("category") == "table" else "СТУЛ"
    f_tag = _font(_FONT_BOLD, 22)
    draw.rectangle([(PADDING, ACCENT_HEIGHT + 10), (PADDING + 110, ACCENT_HEIGHT + 42)], fill=palette["accent"])
    draw.text((PADDING + 56, ACCENT_HEIGHT + 26), cat_text, font=f_tag, fill=(255,255,255), anchor="mm")

    # Brand · article
    f_brand = _font(_FONT_BOLD, 20)
    brand_txt = f"{data.get('brand','')}  ·  арт. {data.get('article','')}"
    draw.text((PADDING + 125, ACCENT_HEIGHT + 26), brand_txt, font=f_brand, fill=palette["muted"], anchor="lm")

    # Slide label (right)
    draw.text((W - PADDING, ACCENT_HEIGHT + 26), slide_label.upper(), font=f_brand, fill=palette["accent"], anchor="rm")

    # Divider
    draw.rectangle([(PADDING, HEADER_H - 4), (W - PADDING, HEADER_H)], fill=palette["accent"])


def _draw_footer(draw: ImageDraw.ImageDraw, data: dict, palette: dict, label: str) -> None:
    draw.rectangle([(0, H - FOOTER_H), (W, H)], fill=palette["accent"])
    f = _font(_FONT_BOLD, 22)
    draw.text((PADDING, H - FOOTER_H//2), data.get("brand","").upper(), font=f, fill=(255,255,255), anchor="lm")
    f2 = _font(_FONT_REGULAR, 18)
    draw.text((W//2, H - FOOTER_H//2), f"{label} — PM-RU Content Agent", font=f2, fill=(180,200,230), anchor="mm")
    draw.text((W - PADDING, H - FOOTER_H//2), data.get("article",""), font=f, fill=(200,220,255), anchor="rm")


# ── Slide renderers ────────────────────────────────────────────────────────────

def render_preview(data: dict, photo: Image.Image | None, palette: dict) -> Image.Image:
    label = "Превью"
    canvas = Image.new("RGB", (W, H), palette["bg"])
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, data, palette, label)

    # Product name
    y = HEADER_H + 14
    f_title = _font(_FONT_BOLD, 40)
    name = data.get("product_name") or data.get("product", {}).get("name", "")
    for line in textwrap.wrap(name, 26):
        draw.text((PADDING, y), line, font=f_title, fill=palette["text"])
        y += 48

    # Variant + dimensions
    f_sub = _font(_FONT_REGULAR, 24)
    variant = data.get("variant", "")
    if variant:
        draw.text((PADDING, y), f"Вариант: {variant}", font=f_sub, fill=palette["muted"])
        y += 32
    dims = _dims_str(data)
    if dims:
        f_dim = _font(_FONT_BOLD, 24)
        draw.text((PADDING, y), dims, font=f_dim, fill=palette["accent"])
        y += 38

    # Photo zone
    photo_top = y + 10
    photo_box = (PADDING, photo_top, W - PADDING, H - FOOTER_H - PHOTO_MARGIN)
    _paste_photo(canvas, photo, photo_box)

    _draw_footer(draw, data, palette, label)
    return canvas


def render_dimensions(data: dict, photo: Image.Image | None, palette: dict) -> Image.Image:
    label = "Размеры"
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, data, palette, label)

    y = HEADER_H + 16
    f_head = _font(_FONT_BOLD, 28)
    draw.text((PADDING, y), "РАЗМЕРЫ И ГАБАРИТЫ", font=f_head, fill=palette["accent"])
    y += 44

    rows = _dimension_rows(data)
    f_label = _font(_FONT_REGULAR, 24)
    f_val   = _font(_FONT_BOLD, 26)
    for i, (lbl, val) in enumerate(rows):
        if not val:
            continue
        bg = palette["row_even"] if i % 2 == 0 else (248, 248, 248)
        draw.rectangle([(PADDING, y), (W - PADDING, y + 52)], fill=bg)
        draw.text((PADDING + 16, y + 26), lbl, font=f_label, fill=palette["muted"], anchor="lm")
        draw.text((W - PADDING - 16, y + 26), val, font=f_val, fill=palette["accent"], anchor="rm")
        y += 56

    # Product photo (small) on the right half
    remaining_top = y + 20
    if remaining_top < H - FOOTER_H - 80:
        mid = W // 2
        photo_box = (mid + 10, remaining_top, W - PADDING, H - FOOTER_H - PHOTO_MARGIN)
        if photo_box[3] > photo_box[1] + 40:
            _paste_photo(canvas, photo, photo_box)
        # Diagram placeholder on left
        diag_box = (PADDING, remaining_top, mid - 10, H - FOOTER_H - PHOTO_MARGIN)
        if diag_box[3] > diag_box[1] + 40:
            draw.rectangle(list(diag_box), fill=palette["accent_lt"], outline=palette["accent"], width=1)
            f_ph = _font(_FONT_REGULAR, 20)
            cx = (diag_box[0] + diag_box[2]) // 2
            cy = (diag_box[1] + diag_box[3]) // 2
            draw.text((cx, cy), "[ Схема ]", font=f_ph, fill=palette["accent"], anchor="mm")

    _draw_footer(draw, data, palette, label)
    return canvas


def render_materials(data: dict, photo: Image.Image | None, palette: dict) -> Image.Image:
    label = "Материалы"
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, data, palette, label)

    y = HEADER_H + 16
    f_head = _font(_FONT_BOLD, 28)
    draw.text((PADDING, y), "МАТЕРИАЛЫ", font=f_head, fill=palette["accent"])
    y += 44

    rows = _material_rows(data)
    f_label = _font(_FONT_REGULAR, 24)
    f_val   = _font(_FONT_BOLD, 24)
    for i, (lbl, val) in enumerate(rows):
        if not val:
            continue
        bg = palette["row_even"] if i % 2 == 0 else (248, 248, 248)
        draw.rectangle([(PADDING, y), (W - PADDING, y + 52)], fill=bg)
        draw.text((PADDING + 16, y + 26), lbl, font=f_label, fill=palette["muted"], anchor="lm")
        draw.text((W - PADDING - 16, y + 26), val, font=f_val, fill=palette["text"], anchor="rm")
        y += 56

    # Photo fills remaining space
    remaining_top = y + 20
    if remaining_top < H - FOOTER_H - 60:
        photo_box = (PADDING + (W - 2*PADDING)//3, remaining_top, W - PADDING, H - FOOTER_H - PHOTO_MARGIN)
        if photo_box[3] > photo_box[1] + 40:
            _paste_photo(canvas, photo, photo_box)

    _draw_footer(draw, data, palette, label)
    return canvas


def render_utp(data: dict, photo: Image.Image | None, palette: dict) -> Image.Image:
    label = "Преимущества"
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, data, palette, label)

    y = HEADER_H + 16
    f_head = _font(_FONT_BOLD, 28)
    draw.text((PADDING, y), "ПРЕИМУЩЕСТВА", font=f_head, fill=palette["accent"])
    y += 44

    utps = [v for k in ["utp_1","utp_2","utp_3","utp_4","utp_5"]
            if (v := (data.get(k) or ""))]
    f_num  = _font(_FONT_BOLD, 26)
    f_body = _font(_FONT_REGULAR, 24)
    for i, utp in enumerate(utps[:5]):
        num_x, num_w = PADDING, 48
        draw.rectangle([(num_x, y), (num_x + num_w, y + 52)], fill=palette["accent"])
        draw.text((num_x + num_w//2, y + 26), str(i+1), font=f_num, fill=(255,255,255), anchor="mm")
        tx = num_x + num_w + 16
        for j, line in enumerate(textwrap.wrap(utp, 34)):
            draw.text((tx, y + j*28 + 14), line, font=f_body, fill=palette["text"])
        row_h = max(52, 28 * len(textwrap.wrap(utp, 34)) + 10)
        y += row_h + 8

    # Interior photo if space
    remaining_top = y + 16
    if remaining_top < H - FOOTER_H - 80:
        photo_box = (PADDING, remaining_top, W - PADDING, H - FOOTER_H - PHOTO_MARGIN)
        _paste_photo(canvas, photo, photo_box)

    _draw_footer(draw, data, palette, label)
    return canvas


# ── Helper functions ───────────────────────────────────────────────────────────

def _dims_str(data: dict) -> str:
    w = data.get("width_cm") or (data.get("text_blocks", {}).get("dimensions", [None])[0])
    d = data.get("depth_cm") or ""
    h = data.get("height_cm") or ""
    parts = [p for p in [w, d, h] if p]
    return f"Ш {parts[0]} × Г {parts[1]} × В {parts[2]} см" if len(parts) >= 3 else ""


def _dimension_rows(data: dict) -> list[tuple[str, str]]:
    rows = [
        ("Ширина",         f"{data.get('width_cm', '')} см" if data.get("width_cm") else ""),
        ("Глубина",        f"{data.get('depth_cm', '')} см" if data.get("depth_cm") else ""),
        ("Высота",         f"{data.get('height_cm', '')} см" if data.get("height_cm") else ""),
        ("Высота сиденья", f"{data.get('seat_height_cm', '')} см" if data.get("seat_height_cm") else ""),
    ]
    return [(l, v) for l, v in rows if v]


def _material_rows(data: dict) -> list[tuple[str, str]]:
    if data.get("category") == "table":
        return [
            ("Столешница",   data.get("tabletop_material", "")),
            ("Цвет/отделка", data.get("tabletop_finish", "")),
            ("Ножки",        data.get("legs_material", "")),
            ("Макс. нагрузка", data.get("max_load", "")),
        ]
    return [
        ("Обивка/ткань",    data.get("fabric_type", "")),
        ("Каркас",          data.get("frame_material", "")),
        ("Макс. нагрузка",  data.get("max_load", "")),
    ]


# ── Public API ─────────────────────────────────────────────────────────────────

def build_slides(
    data: dict,
    photos: Any,   # PhotoSet from yadisk
    out_dir: pathlib.Path,
    article: str = "",
) -> list[str]:
    """
    Render all 4 slides for a product and save to out_dir.
    Returns list of file paths.
    """
    cat = data.get("category", "table")
    palette = PALETTES.get(cat, PALETTES["table"])
    art = (article or data.get("article", "item")).replace("/", "-")

    # Download photos
    preview_img = _download_image(photos.white_front or photos.white_34 or photos.main_photo())
    angle_img   = _download_image(photos.white_34 or photos.white_front or photos.main_photo())
    interior_img = _download_image(photos.interior[0] if photos.interior else "")

    slides = [
        (f"{art}_{cat}_preview.png",    render_preview(data,    preview_img,  palette)),
        (f"{art}_{cat}_dimensions.png", render_dimensions(data, angle_img,    palette)),
        (f"{art}_{cat}_materials.png",  render_materials(data,  angle_img,    palette)),
        (f"{art}_{cat}_utp.png",        render_utp(data,        interior_img, palette)),
    ]

    paths = []
    for fname, img in slides:
        p = out_dir / fname
        img.save(str(p))
        paths.append(str(p))

    return paths
