"""Plan review requests

Revision ID: 003
Revises: 002
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_review_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "reviewer_id", name="uq_plan_reviewer"),
    )
    op.create_index(op.f("ix_plan_review_requests_plan_id"), "plan_review_requests", ["plan_id"])
    op.create_index(
        op.f("ix_plan_review_requests_reviewer_id"), "plan_review_requests", ["reviewer_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_review_requests_reviewer_id"), table_name="plan_review_requests")
    op.drop_index(op.f("ix_plan_review_requests_plan_id"), table_name="plan_review_requests")
    op.drop_table("plan_review_requests")
