"""Add name and updated_at to evaluation_runs (evaluation jobs)

Revision ID: 004
Revises: 003
Create Date: 2026-06-01

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
        "evaluation_runs",
        sa.Column("name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE evaluation_runs
        SET name = 'Eval-' || UPPER(SUBSTRING(REPLACE(id::text, '-', ''), 1, 6))
        WHERE name IS NULL
        """
    )
    op.alter_column("evaluation_runs", "name", nullable=False)


def downgrade() -> None:
    op.drop_column("evaluation_runs", "updated_at")
    op.drop_column("evaluation_runs", "name")
