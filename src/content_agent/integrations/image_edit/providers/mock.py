import structlog

from content_agent.integrations.image_edit.base import ImageEditProvider

logger = structlog.get_logger()


class MockImageEditProvider(ImageEditProvider):
    """Pass-through mock — returns the original image URL unchanged."""

    async def edit(self, image_url: str, prompt: str) -> str:
        logger.info("image_edit.mock", image_url=image_url, prompt=prompt)
        return image_url
