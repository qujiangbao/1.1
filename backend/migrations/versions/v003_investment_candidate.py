"""Add the evidence-based investment decision loop.

Revision ID: 003_investment_candidate
Revises: 002_policy_pgvector
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "003_investment_candidate"
down_revision: Union[str, None] = "002_policy_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investment_scenario",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("industry", sa.String(200), nullable=False),
        sa.Column(
            "target_chain_roles",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("location_preference", sa.String(200)),
        sa.Column("result_limit", sa.Integer(), nullable=False),
        sa.Column("data_mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "recommendation_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "snapshot_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_task_id", sa.String(50)),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_scenario_data_mode",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investment_scenario_mode_created",
        "investment_scenario",
        ["data_mode", "created_at"],
    )

    op.create_table(
        "investment_candidate",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("enterprise_id", sa.String(200), nullable=False),
        sa.Column("enterprise_name", sa.String(500), nullable=False),
        sa.Column(
            "scenario_id",
            sa.String(36),
            sa.ForeignKey("investment_scenario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("industry_chain_role", sa.String(200)),
        sa.Column("overall_score", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column(
            "score_breakdown",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "unknown_fields",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("risk_summary", sa.Text()),
        sa.Column(
            "policy_matches",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("assignee_id", sa.String(50)),
        sa.Column("source_task_id", sa.String(50)),
        sa.Column("data_mode", sa.String(10), nullable=False),
        sa.Column("manual_note", sa.Text()),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_candidate_data_mode",
        ),
        sa.CheckConstraint(
            "risk_level IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')",
            name="ck_candidate_risk_level",
        ),
        sa.CheckConstraint(
            "status IN "
            "('NEW', 'REVIEWED', 'CONTACTING', 'NEGOTIATING', "
            "'REJECTED', 'ARCHIVED')",
            name="ck_candidate_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id",
            "scenario_id",
            "data_mode",
            name="uq_candidate_enterprise_scenario_mode",
        ),
    )
    op.create_index(
        "ix_investment_candidate_mode_status",
        "investment_candidate",
        ["data_mode", "status", "updated_at"],
    )
    op.create_index(
        "ix_investment_candidate_assignee",
        "investment_candidate",
        ["assignee_id", "updated_at"],
    )

    op.create_table(
        "candidate_feedback",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("investment_candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("reviewer_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('ACCEPT', 'REJECT', 'NEED_MORE_EVIDENCE', 'DEFER')",
            name="ck_candidate_feedback_decision",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_feedback_candidate_id",
        "candidate_feedback",
        ["candidate_id"],
    )

    op.create_table(
        "candidate_audit",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("investment_candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(50), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_audit_candidate_id",
        "candidate_audit",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_audit_candidate_id", table_name="candidate_audit")
    op.drop_table("candidate_audit")
    op.drop_index(
        "ix_candidate_feedback_candidate_id",
        table_name="candidate_feedback",
    )
    op.drop_table("candidate_feedback")
    op.drop_index(
        "ix_investment_candidate_assignee",
        table_name="investment_candidate",
    )
    op.drop_index(
        "ix_investment_candidate_mode_status",
        table_name="investment_candidate",
    )
    op.drop_table("investment_candidate")
    op.drop_index(
        "ix_investment_scenario_mode_created",
        table_name="investment_scenario",
    )
    op.drop_table("investment_scenario")
