"""Distinguish a real approval from one the system granted itself

post_done silently self-approves when no review happened, and the UI then rendered that
identically to a colleague pressing Approve. Research on 25k agentic PRs found ~79% pass
through a single pair of eyes, so "someone approved this" is only worth showing if you can
tell which kind of approval it was.

Revision ID: 010
Revises: 009
Create Date: 2026-08-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("approved_on_ship", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "require_peer_approval", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "require_peer_approval")
    op.drop_column("plans", "approved_on_ship")
