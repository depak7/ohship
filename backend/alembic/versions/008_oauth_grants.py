"""Persist MCP OAuth authorization codes and refresh tokens

Without this, a code minted by /oauth/approve on one dyno is invisible to the /token call
that lands on another, and the client sees "authorization code does not exist".

Revision ID: 008
Revises: 007
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_grants",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_oauth_grants_kind", "oauth_grants", ["kind"])
    op.create_index("ix_oauth_grants_expires_at", "oauth_grants", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_oauth_grants_expires_at", table_name="oauth_grants")
    op.drop_index("ix_oauth_grants_kind", table_name="oauth_grants")
    op.drop_table("oauth_grants")
