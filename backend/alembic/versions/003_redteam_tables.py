"""red team tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "redteam_test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("expected_behavior", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="custom"),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_redteam_test_cases_category", "redteam_test_cases", ["category"])
    op.create_index("ix_redteam_test_cases_external_id", "redteam_test_cases", ["external_id"])

    op.create_table(
        "redteam_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column(
            "categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "judge_model",
            sa.String(length=128),
            nullable=False,
            server_default="gemini-2.0-flash",
        ),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uncertain", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "report",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_redteam_runs_agent_id", "redteam_runs", ["agent_id"])
    op.create_index("ix_redteam_runs_status", "redteam_runs", ["status"])

    op.create_table(
        "redteam_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=256), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["redteam_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["test_case_id"], ["redteam_test_cases.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_redteam_results_run_id", "redteam_results", ["run_id"])
    op.create_index("ix_redteam_results_classification", "redteam_results", ["classification"])
    op.create_index("ix_redteam_results_trace_id", "redteam_results", ["trace_id"])
    op.create_index("ix_redteam_results_category", "redteam_results", ["category"])


def downgrade() -> None:
    op.drop_index("ix_redteam_results_category", table_name="redteam_results")
    op.drop_index("ix_redteam_results_trace_id", table_name="redteam_results")
    op.drop_index("ix_redteam_results_classification", table_name="redteam_results")
    op.drop_index("ix_redteam_results_run_id", table_name="redteam_results")
    op.drop_table("redteam_results")
    op.drop_index("ix_redteam_runs_status", table_name="redteam_runs")
    op.drop_index("ix_redteam_runs_agent_id", table_name="redteam_runs")
    op.drop_table("redteam_runs")
    op.drop_index("ix_redteam_test_cases_external_id", table_name="redteam_test_cases")
    op.drop_index("ix_redteam_test_cases_category", table_name="redteam_test_cases")
    op.drop_table("redteam_test_cases")
