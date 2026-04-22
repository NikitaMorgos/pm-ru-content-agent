"""
Smoke test: рендерим первый слайд стола (превью, frame 2:11) с тестовыми данными.
Сохраняем результат в docs/test_slide_preview.png

Запуск:
    python scripts/test_render_slide.py
"""
import io
import os
import pathlib
import sys

sys.path.insert(0, "src")

FIGMA_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")
if not FIGMA_TOKEN:
    # Fallback: read from .env file
    import pathlib as _pl
    env_file = _pl.Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("FIGMA_ACCESS_TOKEN="):
                FIGMA_TOKEN = line.split("=", 1)[1].strip()
                break
FILE_KEY = "6ftFaqPgnvCbCmyjzxDcKI"
FRAME_ID = "2:11"   # table preview 184109_1

FILL_MAP = {
    "product_title":     "2:20",
    "dimensions_hwl":    "2:21",
    "legs_material":     "2:22",
    "brand":             "2:23",
    "utp_assembly":      "2:42",
    "utp_surface":       "2:53",
    "tabletop_finish":   "2:58",
    "tabletop_material": "2:59",
}

TEXT_VALUES = {
    "product_title":     "Кухонный стол / до 4 персон",
    "dimensions_hwl":    "75 × 90 × 66 см",
    "legs_material":     "Металлические ножки",
    "brand":             "БЕННИ",
    "utp_assembly":      "Можно собрать самостоятельно",
    "utp_surface":       "Влагостойкая поверхность",
    "tabletop_finish":   "Матовая столешница",
    "tabletop_material": "ЛДСП 22 мм",
}

OUT_PATH = pathlib.Path("docs/test_slide_preview.png")


def main() -> None:
    from content_agent.integrations.figma.client import FigmaClient
    from content_agent.integrations.figma.renderer import extract_text_layers, render_slide

    client = FigmaClient(token=FIGMA_TOKEN)

    print("1. Экспортируем шаблон из Figma...")
    png_bytes = client.export_frame_png(FILE_KEY, FRAME_ID, scale=2.0)
    print(f"   OK — {len(png_bytes):,} bytes")

    print("2. Получаем метаданные слоёв...")
    frame_doc = client.get_frame_node(FILE_KEY, FRAME_ID)
    bbox = frame_doc.get("absoluteBoundingBox", {})
    print(f"   Frame bbox: {bbox}")

    print("3. Извлекаем TEXT-слои...")
    text_layers = extract_text_layers(
        frame_doc=frame_doc,
        fill_map=FILL_MAP,
        frame_abs_x=bbox.get("x", 0),
        frame_abs_y=bbox.get("y", 0),
        export_scale=2.0,
    )
    for field, layer in text_layers.items():
        print(f"   {field}: px=({layer.px},{layer.py}) size=({layer.pw}x{layer.ph})"
              f" font={layer.font_family} {layer.font_size:.0f}px w={layer.font_weight}"
              f" color={layer.fill_rgba}")

    print("4. Рендерим финальный слайд...")
    result_png = render_slide(
        template_png_bytes=png_bytes,
        text_layers=text_layers,
        text_values=TEXT_VALUES,
    )
    print(f"   OK — {len(result_png):,} bytes")

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_bytes(result_png)
    print(f"\n✓ Сохранено: {OUT_PATH.resolve()}")
    print("  Открой файл и проверь что текст заменился корректно.")


if __name__ == "__main__":
    main()
