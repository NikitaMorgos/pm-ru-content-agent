"""Redmine REST API client."""

from typing import Any

import structlog
from httpx import Client

from content_agent.config import settings
from content_agent.integrations.redmine.schemas import parse_redmine_issue

logger = structlog.get_logger()

# Custom field names — Redmine field names (Russian) mapped to internal keys
# Source of truth: docs/task_management.md — Redmine Custom Fields Schema

CF_CARD_TYPE = "Тип карточки"
CF_MAIN_IMAGE_URL = "URL главного изображения"
CF_PRODUCT_SKU = "Артикул"
CF_BRIEF_TEXT = "Текст на карточке"
CF_COLOR_SCHEME = "Цветовое решение"
CF_SEGMENT = "Сегмент инфографики"
CF_MARKETPLACE = "Маркетплейс"
CF_IMAGE_NUMBER = "Номер изображения в карточке"
CF_RENDER_URL = "Рендер"
CF_COMMENT = "Комментарий"
CF_PHOTO_REFERENCE_URL = "Фотореференс"
CF_IMAGE_FORMAT = "Формат изображения"
CF_VARIANT = "Вариант"
CF_JOB_ID = "ID"


class RedmineClient:
    """Sync HTTP client for Redmine REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.redmine_base_url).rstrip("/")
        self.api_key = api_key or settings.redmine_api_key.get_secret_value()
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(
                base_url=self.base_url,
                headers={
                    "X-Redmine-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_issue(self, issue_id: int) -> dict:
        """
        Fetch a single issue by ID.
        Returns raw dict as returned by Redmine API (for flexibility).
        """
        client = self._get_client()
        url = f"/issues/{issue_id}.json"
        logger.debug("redmine.get_issue", issue_id=issue_id)
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
        return data

    def get_issue_parsed(self, issue_id: int):
        """Fetch a single issue and return parsed RedmineIssue."""
        data = self.get_issue(issue_id)
        return parse_redmine_issue(data)

    def update_issue(
        self,
        issue_id: int,
        *,
        status_id: int | None = None,
        notes: str | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> dict:
        """
        Update an issue. Returns raw response dict.
        """
        client = self._get_client()
        url = f"/issues/{issue_id}.json"
        body: dict[str, Any] = {"issue": {}}
        if status_id is not None:
            body["issue"]["status_id"] = status_id
        if notes is not None:
            body["issue"]["notes"] = notes
        if custom_fields is not None:
            body["issue"]["custom_fields"] = custom_fields

        logger.debug("redmine.update_issue", issue_id=issue_id)
        response = client.put(url, json=body)
        response.raise_for_status()
        return response.json()

    def add_journal_note(self, issue_id: int, notes: str) -> dict:
        """Add a journal note (comment) to an issue."""
        return self.update_issue(issue_id, notes=notes)
