"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("row_count_raw", sa.Integer, nullable=False, server_default="0"),
        sa.Column("row_count_clean", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("txn_id", sa.String(50), nullable=True),
        sa.Column("date", sa.DATE, nullable=False),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("account_id", sa.String(20), nullable=False),
        sa.Column("is_anomaly", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("anomaly_reason", sa.Text, nullable=True),
        sa.Column("llm_failed", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_transactions_job_id", "transactions", ["job_id"])

    op.create_table(
        "job_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("top_merchants", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("total_spend_inr", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_spend_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("anomaly_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="low"),
    )


def downgrade() -> None:
    op.drop_table("job_summaries")
    op.drop_table("transactions")
    op.drop_table("jobs")
