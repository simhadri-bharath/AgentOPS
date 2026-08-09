"""Dataset lifecycle fields

Revision ID: 006
Revises: 005
Create Date: 2026-08-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="upload"),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="human_reviewed",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("datasets", sa.Column("created_by", sa.String(length=255), nullable=True))
    op.add_column(
        "datasets",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "category_distribution",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_datasets_agent_id", "datasets", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_datasets_agent_id", table_name="datasets")
    op.drop_column("datasets", "category_distribution")
    op.drop_column("datasets", "agent_id")
    op.drop_column("datasets", "created_by")
    op.drop_column("datasets", "version")
    op.drop_column("datasets", "review_status")
    op.drop_column("datasets", "source")
