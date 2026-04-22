"""TaskManifestRecord model for storing manifest snapshots."""

from sqlalchemy import ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from content_agent.db.base import Base


class TaskManifestRecord(Base):
    """Stored manifest snapshot per pipeline step."""

    __tablename__ = "task_manifests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)

    # relationship
    job = relationship("Job", back_populates="manifest_records")
