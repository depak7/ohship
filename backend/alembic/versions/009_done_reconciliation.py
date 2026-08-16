"""Record per-criterion outcomes on Done

Acceptance criteria were an opaque text blob, so a Done summary could quietly omit a
criterion and the plan would still look shipped. This stores what actually happened to each
one — met, changed, dropped or unreported — so drift is visible instead of inferred.

Revision ID: 009
Revises: 008
Create Date: 2026-08-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "done_records",
        sa.Column("reconciliation", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("done_records", "reconciliation")
