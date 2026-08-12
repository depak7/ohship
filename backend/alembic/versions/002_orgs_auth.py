"""Add orgs, invites, auth fields

Revision ID: 002
Revises: 001
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    op.alter_column("users", "api_key_hash", existing_type=sa.String(length=255), nullable=True)
    op.create_index(op.f("ix_users_google_id"), "users", ["google_id"], unique=False)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "org_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )
    op.create_index(op.f("ix_org_memberships_organization_id"), "org_memberships", ["organization_id"])
    op.create_index(op.f("ix_org_memberships_user_id"), "org_memberships", ["user_id"])

    op.create_table(
        "invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invites_organization_id"), "invites", ["organization_id"])
    op.create_index(op.f("ix_invites_token"), "invites", ["token"], unique=True)

    # Backfill: create a default org for existing plans if any users exist
    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id FROM users ORDER BY created_at LIMIT 1")).fetchall()
    if users:
        owner_id = users[0][0]
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, slug, created_by_id, created_at) "
                "VALUES (gen_random_uuid(), 'Default', 'default', :uid, NOW()) RETURNING id"
            ),
            {"uid": owner_id},
        ).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO org_memberships (id, organization_id, user_id, role, joined_at) "
                "VALUES (gen_random_uuid(), :oid, :uid, 'owner', NOW())"
            ),
            {"oid": org_id, "uid": owner_id},
        )
        op.add_column("plans", sa.Column("organization_id", sa.Uuid(), nullable=True))
        conn.execute(
            sa.text("UPDATE plans SET organization_id = :oid WHERE organization_id IS NULL"),
            {"oid": org_id},
        )
        op.alter_column("plans", "organization_id", nullable=False)
    else:
        op.add_column("plans", sa.Column("organization_id", sa.Uuid(), nullable=False))

    op.create_foreign_key(
        "fk_plans_organization_id", "plans", "organizations", ["organization_id"], ["id"]
    )
    op.create_index(op.f("ix_plans_organization_id"), "plans", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_plans_organization_id"), table_name="plans")
    op.drop_constraint("fk_plans_organization_id", "plans", type_="foreignkey")
    op.drop_column("plans", "organization_id")
    op.drop_index(op.f("ix_invites_token"), table_name="invites")
    op.drop_index(op.f("ix_invites_organization_id"), table_name="invites")
    op.drop_table("invites")
    op.drop_index(op.f("ix_org_memberships_user_id"), table_name="org_memberships")
    op.drop_index(op.f("ix_org_memberships_organization_id"), table_name="org_memberships")
    op.drop_table("org_memberships")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")
    op.drop_index(op.f("ix_users_google_id"), table_name="users")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "google_id")
    op.drop_column("users", "password_hash")
    op.alter_column("users", "api_key_hash", existing_type=sa.String(length=255), nullable=False)
