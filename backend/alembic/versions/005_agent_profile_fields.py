"""Add purpose/type/capability/environment fields to agents

Revision ID: 005
Revises: 004
Create Date: 2026-08-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "agent_type",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column("agents", sa.Column("purpose", sa.Text(), nullable=True))
    op.add_column(
        "agents",
        sa.Column(
            "environment",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "invocation_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_agents_agent_type", "agents", ["agent_type"])
    op.create_index("ix_agents_environment", "agents", ["environment"])


def downgrade() -> None:
    op.drop_index("ix_agents_environment", table_name="agents")
    op.drop_index("ix_agents_agent_type", table_name="agents")
    op.drop_column("agents", "invocation_config")
    op.drop_column("agents", "environment")
    op.drop_column("agents", "purpose")
    op.drop_column("agents", "capabilities")
    op.drop_column("agents", "agent_type")
