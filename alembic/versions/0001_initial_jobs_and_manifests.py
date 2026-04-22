"""initial jobs and manifests

Revision ID: 0001
Revises:
Create Date: 2026-03-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=False),
        sa.Column("redmine_issue_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("step", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_celery_task_id"), "jobs", ["celery_task_id"], unique=True)
    op.create_index(op.f("ix_jobs_redmine_issue_id"), "jobs", ["redmine_issue_id"], unique=False)

    op.create_table(
        "task_manifests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("task_manifests")
    op.drop_index(op.f("ix_jobs_redmine_issue_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_celery_task_id"), table_name="jobs")
    op.drop_table("jobs")
