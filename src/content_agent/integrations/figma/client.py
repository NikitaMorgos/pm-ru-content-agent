"""Figma REST API client — read nodes, export PNG."""
from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

FIGMA_API = "https://api.figma.com/v1"


class FigmaClient:
    def __init__(self, token: str) -> None:
        self._token = token
        self._headers = {"X-Figma-Token": token}

    # ── Node data ──────────────────────────────────────────────────────────

    def get_nodes(self, file_key: str, node_ids: list[str], depth: int = 4) -> dict:
        """Return raw nodes dict from Figma API."""
        ids_param = ",".join(node_ids)
        url = f"{FIGMA_API}/files/{file_key}/nodes"
        resp = httpx.get(
            url,
            headers=self._headers,
            params={"ids": ids_param, "depth": depth},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["nodes"]

    def get_frame_node(self, file_key: str, frame_id: str) -> dict:
        """Return document node for a single frame with full style data."""
        nodes = self.get_nodes(file_key, [frame_id], depth=4)
        key = frame_id  # Figma returns keys as given
        return nodes[key]["document"]

    # ── Image export ───────────────────────────────────────────────────────

    def export_frame_png(
        self,
        file_key: str,
        frame_id: str,
        scale: float = 2.0,
    ) -> bytes:
        """Export a Figma frame as PNG bytes at the given scale."""
        url = f"{FIGMA_API}/images/{file_key}"
        resp = httpx.get(
            url,
            headers=self._headers,
            params={"ids": frame_id, "format": "png", "scale": scale},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data["images"].get(frame_id)
        if not image_url:
            raise RuntimeError(f"Figma returned no image URL for frame {frame_id}")

        logger.info("figma.export.downloading", url=image_url[:80])
        img_resp = httpx.get(image_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content
