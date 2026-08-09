"""Add governed policy-crawler access and run audit tables.

Revision ID: 008_policy_crawler
Revises: 007_recommendation_exposure
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "008_policy_crawler"
down_revision: Union[str, None] = "007_recommendation_exposure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_crawler_access_requests",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column(
            "requester_id",
            sa.String(50),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("decided_by", sa.String(50), sa.ForeignKey("users.user_id")),
        sa.Column("decision_note", sa.Text()),
        sa.Column(
            "requested_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("decided_at", sa.DateTime()),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_policy_crawler_request_status",
        ),
    )
    op.create_index(
        "ix_policy_crawler_requester_status",
        "policy_crawler_access_requests",
        ["requester_id", "status"],
    )

    op.create_table(
        "policy_crawler_grants",
        sa.Column(
            "user_id",
            sa.String(50),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="APPROVED"),
        sa.Column("approved_by", sa.String(50), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column(
            "approved_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("revoked_by", sa.String(50), sa.ForeignKey("users.user_id")),
        sa.Column("revoked_at", sa.DateTime()),
        sa.CheckConstraint(
            "status IN ('APPROVED', 'REVOKED')",
            name="ck_policy_crawler_grant_status",
        ),
    )

    op.create_table(
        "policy_crawl_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("requested_by", sa.String(50), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("workers", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("force", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED')",
            name="ck_policy_crawl_run_status",
        ),
        sa.CheckConstraint("pages BETWEEN 1 AND 20", name="ck_policy_crawl_pages"),
        sa.CheckConstraint("workers BETWEEN 1 AND 3", name="ck_policy_crawl_workers"),
    )
    op.create_index(
        "ix_policy_crawl_runs_created_at",
        "policy_crawl_runs",
        ["created_at"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_policy_crawl_active_run "
        "ON policy_crawl_runs ((1)) WHERE status IN ('QUEUED', 'RUNNING')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_policy_crawl_active_run")
    op.drop_index("ix_policy_crawl_runs_created_at", table_name="policy_crawl_runs")
    op.drop_table("policy_crawl_runs")
    op.drop_table("policy_crawler_grants")
    op.drop_index(
        "ix_policy_crawler_requester_status",
        table_name="policy_crawler_access_requests",
    )
    op.drop_table("policy_crawler_access_requests")
