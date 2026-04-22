"""FillJob — задание на рендеринг для Figma-плагина."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from content_agent.db.base import Base


class FillJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    TIMEOUT = "timeout"


class FillJob(Base):
    """One render job = one output slide PNG.

    Created by fill_figma_template Celery task.
    Consumed by the Figma plugin running on the render workstation.
    """

    __tablename__ = "fill_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("jobs.id"), nullable=False, index=True)

    # Figma location
    file_key: Mapped[str] = mapped_column(String(64), nullable=False)
    frame_id: Mapped[str] = mapped_column(String(32), nullable=False)
    slide_type: Mapped[str] = mapped_column(String(64), nullable=False)
    slide_index: Mapped[int] = mapped_column(default=0)  # order within a job

    # Fill instructions: {node_id: text_value}
    text_fills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Image fills: {node_id: image_url}  (future: images in slides)
    image_fills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Status tracking
    status: Mapped[FillJobStatus] = mapped_column(
        Enum(FillJobStatus), default=FillJobStatus.PENDING, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    plugin_instance_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Result: storage key of the exported PNG
    result_storage_key: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<FillJob {self.id} slide={self.slide_type} status={self.status}>"
