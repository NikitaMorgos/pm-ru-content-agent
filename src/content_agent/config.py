from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database — optional for admin-only / demo mode
    database_url: str = "sqlite:///./content_agent_demo.db"

    # Redis / Celery — optional; tasks run in-process without broker
    redis_url: str = "redis://localhost:6379/0"

    # Redmine — optional for admin-only mode
    redmine_base_url: str = "https://project.pm.ru"
    redmine_api_key: SecretStr = SecretStr("")

    # Figma — set FIGMA_ACCESS_TOKEN to enable real rendering
    figma_access_token: SecretStr = SecretStr("")
    figma_template_registry_path: str = "config/template_registry.json"

    # Storage — optional; slides served from local temp dir until S3 is connected
    storage_endpoint_url: str = ""
    storage_bucket: str = ""
    aws_access_key_id: SecretStr = SecretStr("")
    aws_secret_access_key: SecretStr = SecretStr("")
    storage_region: str = "ru-central1"

    # LLM — optional; normalize/compress steps are stubs until connected
    openai_api_key: SecretStr = SecretStr("")
    llm_provider: Literal["openai", "mock"] = "mock"

    # Image Edit
    image_edit_provider: Literal["mock", "openai_dalle"] = "mock"

    # API auth — set a real key in production
    api_key: SecretStr = SecretStr("demo")

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
