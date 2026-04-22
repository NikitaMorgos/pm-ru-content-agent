from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class CardType(StrEnum):
    HERO = "hero"
    DIMENSIONS = "dimensions"
    COLORS = "colors"
    SIMPLE_BENEFIT = "simple_benefit"


class ProductInfo(BaseModel):
    sku: str
    name: str
    brand: str = ""


class AssetInfo(BaseModel):
    main_image_url: HttpUrl
    icons: list[HttpUrl] = Field(default_factory=list)
    color_swatches: list[HttpUrl] = Field(default_factory=list)


class TextBlocks(BaseModel):
    title: str = ""
    description: str = ""
    benefits: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    color_names: list[str] = Field(default_factory=list)


class FigmaInfo(BaseModel):
    template_id: str | None = None
    file_key: str | None = None
    frame_id: str | None = None
    fill_map: dict[str, Any] = Field(default_factory=dict)


class OutputInfo(BaseModel):
    png_url: str | None = None
    storage_key: str | None = None


class ManifestMeta(BaseModel):
    redmine_issue_id: int
    job_id: str
    pipeline_step: str = "created"
    # Redmine fields
    variant: str | None = None
    marketplace: str | None = None
    segment: str | None = None
    image_number: str | None = None
    image_format: str = "png"
    color_scheme: str | None = None
    comment: str | None = None
    photo_reference_url: str | None = None
    # Pipeline flags
    image_edit_enabled: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TaskManifest(BaseModel):
    task_id: str
    card_type: CardType
    product: ProductInfo
    assets: AssetInfo
    text_blocks: TextBlocks = Field(default_factory=TextBlocks)
    figma: FigmaInfo = Field(default_factory=FigmaInfo)
    output: OutputInfo = Field(default_factory=OutputInfo)
    meta: ManifestMeta
