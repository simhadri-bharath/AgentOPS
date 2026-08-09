"""Run reproducibility snapshot and per-sample metric diagnostics

Revision ID: 007
Revises: 006
Create Date: 2026-08-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb(default: str) -> sa.Column:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("run_config", _jsonb("{}"), nullable=False, server_default="{}"),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("usage", _jsonb("{}"), nullable=False, server_default="{}"),
    )

    op.add_column(
        "evaluation_results",
        sa.Column("metric_explanations", _jsonb("{}"), nullable=False, server_default="{}"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("metric_unavailable", _jsonb("{}"), nullable=False, server_default="{}"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("metric_errors", _jsonb("{}"), nullable=False, server_default="{}"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("span_scores", _jsonb("[]"), nullable=False, server_default="[]"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("trace", _jsonb("{}"), nullable=False, server_default="{}"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("state", sa.String(length=32), nullable=False, server_default="SUCCESS"),
    )
    op.add_column("evaluation_results", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_results",
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    for column in (
        "tokens_out",
        "tokens_in",
        "error_message",
        "state",
        "trace",
        "span_scores",
        "metric_errors",
        "metric_unavailable",
        "metric_explanations",
    ):
        op.drop_column("evaluation_results", column)
    op.drop_column("evaluation_runs", "usage")
    op.drop_column("evaluation_runs", "run_config")
