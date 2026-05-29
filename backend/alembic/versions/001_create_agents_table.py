"""create agents table

Revision ID: 001
Revises:
Create Date: 2026-05-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=True),
        sa.Column("deployment_type", sa.String(length=64), nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("gcp_project", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index("ix_agents_name", "agents", ["name"])
    op.create_index("ix_agents_deployment_type", "agents", ["deployment_type"])
    op.create_index("ix_agents_endpoint_url", "agents", ["endpoint_url"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agents_endpoint_url", table_name="agents")
    op.drop_index("ix_agents_deployment_type", table_name="agents")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")
