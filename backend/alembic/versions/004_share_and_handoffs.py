"""Share visibility and done handoffs

Revision ID: 004
Revises: 003
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="team"),
    )
    op.add_column("plans", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_plans_visibility"), "plans", ["visibility"], unique=False)
    op.create_index(op.f("ix_plans_share_token"), "plans", ["share_token"], unique=True)

    op.create_table(
        "done_handoffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("done_record_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["done_record_id"], ["done_records.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("done_record_id", "user_id", name="uq_done_handoff_user"),
    )
    op.create_index(op.f("ix_done_handoffs_done_record_id"), "done_handoffs", ["done_record_id"])
    op.create_index(op.f("ix_done_handoffs_user_id"), "done_handoffs", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_done_handoffs_user_id"), table_name="done_handoffs")
    op.drop_index(op.f("ix_done_handoffs_done_record_id"), table_name="done_handoffs")
    op.drop_table("done_handoffs")
    op.drop_index(op.f("ix_plans_share_token"), table_name="plans")
    op.drop_index(op.f("ix_plans_visibility"), table_name="plans")
    op.drop_column("plans", "share_token")
    op.drop_column("plans", "visibility")
