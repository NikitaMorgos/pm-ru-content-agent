from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str = "image/png") -> str:
        """Upload data to storage and return the public URL."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if an object exists at the given key."""
