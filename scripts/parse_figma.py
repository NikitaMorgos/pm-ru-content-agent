"""Parse Figma API JSON and print layer structure with proper Cyrillic."""
import json
import sys

NODES_FILE = "docs/figma_nodes.json"
STRUCTURE_FILE = "docs/figma_structure.json"


def show_layers(node, indent=0):
    pad = "  " * indent
    name = node.get("name", "")
    ntype = node.get("type", "")
    nid = node.get("id", "")
    chars = node.get("characters", "")
    if chars:
        chars_short = chars[:60].replace("\n", "\\n")
        extra = f'  chars="{chars_short}"'
    else:
        extra = ""
    print(f"{pad}[{ntype}] {name!r}  id={nid}{extra}")
    for child in node.get("children", []):
        show_layers(child, indent + 1)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "structure"

    if mode == "structure":
        with open(STRUCTURE_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
        for page in data["document"]["children"]:
            print(f"\n=== PAGE: {page['name']}  id={page['id']} ===")
            for child in page.get("children", []):
                chars = child.get("characters", "")
                chars_str = f'  >> "{chars[:60].replace(chr(10), " ")}"' if chars else ""
                print(f"  [{child['type']}] {child['name']}  id={child['id']}{chars_str}")

    elif mode == "nodes":
        with open(NODES_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
        for node_id, node_data in data["nodes"].items():
            print(f"\n{'='*60}")
            print(f"NODE: {node_id}")
            show_layers(node_data["document"])

    elif mode == "text_layers":
        # Extract all TEXT nodes from nodes file
        with open(NODES_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)

        def collect_text(node, path=""):
            results = []
            current_path = f"{path}/{node.get('name', '')}"
            if node.get("type") == "TEXT":
                results.append({
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "chars": node.get("characters", ""),
                    "path": current_path,
                })
            for child in node.get("children", []):
                results.extend(collect_text(child, current_path))
            return results

        for node_id, node_data in data["nodes"].items():
            doc = node_data["document"]
            print(f"\n{'='*60}")
            print(f"FRAME: {doc.get('name')}  (node_id={node_id})")
            texts = collect_text(doc)
            for t in texts:
                chars = t["chars"][:80].replace("\n", "\\n")
                print(f"  TEXT  id={t['id']}  name={t['name']!r}")
                print(f"        sample: {chars!r}")


if __name__ == "__main__":
    main()
