from abc import ABC, abstractmethod


class ImageEditProvider(ABC):
    @abstractmethod
    async def edit(self, image_url: str, prompt: str) -> str:
        """Apply an edit to the image and return the URL of the edited image."""
