"""Job model for pipeline tracking."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from content_agent.db.base import Base


class Job(Base):
    """Pipeline job record."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    celery_task_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    redmine_issue_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # relationship
    manifest_records = relationship(
        "TaskManifestRecord", back_populates="job", cascade="all, delete-orphan"
    )
