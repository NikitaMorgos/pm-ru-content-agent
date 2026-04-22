# Figma Conventions — PM-RU Content Agent

## Overview

All Figma templates used by the pipeline must follow a strict layer naming convention.
This ensures the `FigmaFiller` can reliably map manifest fields to template layers.

---

## Layer Naming Convention

| Prefix | Purpose | Example | Manifest Field |
|--------|---------|---------|----------------|
| `TEXT_` | Text layers (auto-filled) | `TEXT_TITLE`, `TEXT_DESCRIPTION`, `TEXT_BENEFIT_1` | `text_blocks.*` |
| `IMG_MAIN` | Main product image | `IMG_MAIN` | `assets.main_image_url` |
| `IMG_ICON_` | Icon layers | `IMG_ICON_1`, `IMG_ICON_2` | `assets.icons[]` |
| `COLOR_SWATCH_` | Color swatch layers | `COLOR_SWATCH_1`, `COLOR_SWATCH_2` | `assets.colors[]` |

---

## Card-Type-Specific Layers

### hero
- `TEXT_TITLE` — product title (≤ 60 chars)
- `IMG_MAIN` — main product shot
- `TEXT_DESCRIPTION` (optional) — short description (≤ 200 chars)

### dimensions
- `TEXT_TITLE` — product name
- `IMG_MAIN` — dimension diagram
- `TEXT_DIM_1` … `TEXT_DIM_6` — dimension labels (3–6 entries)

### colors
- `TEXT_TITLE` — product name
- `COLOR_SWATCH_1` … `COLOR_SWATCH_8` — color fills (2–8 swatches)
- `TEXT_COLOR_1` … `TEXT_COLOR_8` — color names (≤ 20 chars each)

### simple_benefit
- `TEXT_TITLE` — benefit headline (≤ 60 chars)
- `TEXT_BENEFIT` — benefit description (≤ 80 chars)
- `IMG_ICON_1` — benefit icon
- `IMG_MAIN` — supporting image

---

## Template Registry

Templates are registered in `config/template_registry.json`:

```json
{
  "hero": {
    "file_key": "abc123",
    "frame_id": "1:23",
    "version": "v1.0",
    "description": "Main product hero shot"
  }
}
```

- `file_key` — Figma file ID
- `frame_id` — node ID of the frame to fill and export
- `version` — pinned for audit (optional)

---

## Rules

1. **Never modify template files** — only fill instances/frames via API
2. **Export frame IDs** — must be pinned in registry, never derived dynamically
3. **Layer names are case-sensitive** — use exact `TEXT_*`, `IMG_*`, `COLOR_*` prefixes
4. **Missing layers** — if a layer is absent, filler logs warning and skips; pipeline continues if non-critical

---

## Figma API Notes

- **Export**: `GET /images/:file_key?ids=:frame_id&format=png&scale=2`
- **Rate limits**: implement exponential backoff on 429
- **Text updates**: via Figma Variables API or `POST /files/:key/nodes` (depends on Figma API capabilities)
