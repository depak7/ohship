"""Plan notify requests (notify on done)

Revision ID: 006
Revises: 005
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_notify_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("notify_user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notify_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "notify_user_id", name="uq_plan_notify_user"),
    )
    op.create_index(op.f("ix_plan_notify_requests_plan_id"), "plan_notify_requests", ["plan_id"])
    op.create_index(
        op.f("ix_plan_notify_requests_notify_user_id"), "plan_notify_requests", ["notify_user_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_notify_requests_notify_user_id"), table_name="plan_notify_requests")
    op.drop_index(op.f("ix_plan_notify_requests_plan_id"), table_name="plan_notify_requests")
    op.drop_table("plan_notify_requests")
