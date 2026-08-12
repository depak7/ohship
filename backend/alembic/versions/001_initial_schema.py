"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("project", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["claimed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plans_claimed_by_id"), "plans", ["claimed_by_id"], unique=False)
    op.create_index(op.f("ix_plans_owner_id"), "plans", ["owner_id"], unique=False)
    op.create_index(op.f("ix_plans_project"), "plans", ["project"], unique=False)
    op.create_index(op.f("ix_plans_status"), "plans", ["status"], unique=False)
    op.create_index(op.f("ix_plans_team"), "plans", ["team"], unique=False)

    op.create_table(
        "suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suggestions_plan_id"), "suggestions", ["plan_id"], unique=False)

    op.create_table(
        "done_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("links", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("residual_notes", sa.Text(), nullable=True),
        sa.Column("posted_by_id", sa.Uuid(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["posted_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_done_records_plan_id"), "done_records", ["plan_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_done_records_plan_id"), table_name="done_records")
    op.drop_table("done_records")
    op.drop_index(op.f("ix_suggestions_plan_id"), table_name="suggestions")
    op.drop_table("suggestions")
    op.drop_index(op.f("ix_plans_team"), table_name="plans")
    op.drop_index(op.f("ix_plans_status"), table_name="plans")
    op.drop_index(op.f("ix_plans_project"), table_name="plans")
    op.drop_index(op.f("ix_plans_owner_id"), table_name="plans")
    op.drop_index(op.f("ix_plans_claimed_by_id"), table_name="plans")
    op.drop_table("plans")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
