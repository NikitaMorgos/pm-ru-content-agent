"""Pydantic schemas for Redmine API responses."""

from typing import Any

from pydantic import BaseModel, Field


class RedmineCustomField(BaseModel):
    """Redmine custom field item from issue response."""

    id: int
    name: str
    value: str | list | bool | int | None = None


class RedmineIssue(BaseModel):
    """Redmine issue JSON response (simplified for our needs)."""

    id: int
    subject: str = ""
    description: str | None = None
    custom_fields: list[RedmineCustomField] = Field(default_factory=list, alias="custom_fields")

    model_config = {"populate_by_name": True}

    def get_custom_field_value(self, name: str) -> str | list | bool | int | None:
        """Get custom field value by name (case-insensitive)."""
        name_lower = name.lower()
        for cf in self.custom_fields:
            if cf.name.lower() == name_lower:
                return cf.value
        return None

    def get_custom_field_str(self, name: str) -> str | None:
        """Get custom field as string, or None if absent."""
        val = self.get_custom_field_value(name)
        if val is None:
            return None
        if isinstance(val, list):
            val = val[0] if val else None
        if val is None:
            return None
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val).strip() if val else None

    def get_custom_field_bool(self, name: str) -> bool:
        """Get custom field as bool. Default False if absent."""
        val = self.get_custom_field_value(name)
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes", "on")
        return bool(val)


def parse_redmine_issue(data: dict[str, Any]) -> RedmineIssue:
    """Parse raw Redmine API response into RedmineIssue."""
    # Redmine returns issue wrapped in "issue" key for single issue
    if "issue" in data:
        data = data["issue"]
    return RedmineIssue.model_validate(data)
