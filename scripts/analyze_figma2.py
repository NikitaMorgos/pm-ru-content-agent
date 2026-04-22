"""
Analyze remaining chair slides (190870_3-8) and generic chair templates.
"""
import json


def collect_all(node, path="", collect_images=True):
    results = {"texts": [], "images": []}
    current_path = f"{path}/{node.get('name', '')}"
    ntype = node.get("type", "")
    if ntype == "TEXT":
        results["texts"].append({
            "id": node.get("id"),
            "name": node.get("name"),
            "chars": node.get("characters", ""),
        })
    if ntype == "RECTANGLE" and collect_images:
        name = node.get("name", "")
        if "image" in name.lower() or "фото" in name.lower() or "photo" in name.lower() or "mockup" in name.lower():
            results["images"].append({"id": node.get("id"), "name": name})
    for child in node.get("children", []):
        sub = collect_all(child, current_path, collect_images)
        results["texts"].extend(sub["texts"])
        results["images"].extend(sub["images"])
    return results


def main():
    with open("docs/figma_nodes2.json", encoding="utf-8-sig") as f:
        data = json.load(f)

    # Friendly names for chair slides
    known = {
        "4:2104": "190870_3",
        "4:2145": "190870_6",
        "4:2232": "190870_5",
        "4:2263": "190870_1.4",
        "4:2296": "190870_7",
        "4:2322": "190870_8",
        "4:2356": "190870_4",
        "4:1762": "ткань (generic 1)",
        "4:1754": "спинка",
        "4:1710": "антикоготь",
        "4:1994": "интерьер",
        "4:1807": "дизайн",
        "4:1811": "сборка",
        "4:1844": "комплект",
        "4:1853": "стул (generic)",
    }

    lines = ["# Дополнительные слайды стульев — Анализ текстовых слоёв", ""]

    for nid, friendly in known.items():
        node_data = data["nodes"].get(nid)
        if not node_data:
            lines.append(f"\n## {friendly} (id={nid}) — НЕ НАЙДЕН")
            continue
        doc = node_data["document"]
        content = collect_all(doc)
        lines.append(f"\n## [{nid}] {friendly}")
        if content["texts"]:
            lines.append("### TEXT-слои:")
            for t in content["texts"]:
                chars = t["chars"].replace("\n", " / ").replace("\u2028", " ")
                lines.append(f"  • [{t['id']}] name={t['name']!r}")
                lines.append(f"    sample: {chars!r}")
        else:
            lines.append("  (нет TEXT-слоёв)")
        if content["images"]:
            lines.append("### IMAGE-заглушки (RECTANGLE с 'image' в имени):")
            for img in content["images"]:
                lines.append(f"  • [{img['id']}] {img['name']!r}")

    # Also check image placeholders in table preview
    lines.append("\n\n---\n## Итоговая таблица маппинга для 190870 (все слайды)")
    lines.append("""
| Фрейм         | node_id  | Назначение           | TEXT-поля                              |
|---------------|----------|----------------------|----------------------------------------|
| 190870_1.1    | 4:2387   | Превью (вар.1)       | бренд, тип, нагрузка, УТП, ткань      |
| 190870_1.2    | 4:2420   | Превью (вар.2)       | аналогично 1.1                         |
| 190870_1.3    | 4:2453   | Превью (вар.3)       | аналогично 1.1                         |
| 190870_1.4    | 4:2263   | Превью (вар.4)       | аналогично 1.1                         |
| 190870_2      | 4:2339   | Габариты             | ширина, глубина, высота, выс.сиденья   |
| 190870_3      | 4:2104   | (см. анализ выше)    |                                        |
| 190870_4      | 4:2356   | (см. анализ выше)    |                                        |
| 190870_5      | 4:2232   | (см. анализ выше)    |                                        |
| 190870_6      | 4:2145   | (см. анализ выше)    |                                        |
| 190870_7      | 4:2296   | (см. анализ выше)    |                                        |
| 190870_8      | 4:2322   | (см. анализ выше)    |                                        |
""")

    output = "\n".join(lines)
    with open("docs/figma_chair_slides_spec.md", "w", encoding="utf-8") as f:
        f.write(output)
    print("Saved: docs/figma_chair_slides_spec.md")


if __name__ == "__main__":
    main()
