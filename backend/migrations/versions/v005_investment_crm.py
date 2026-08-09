"""Add real investment CRM events and follow-up tasks.

Revision ID: 005_investment_crm
Revises: 004_investment_agent_outputs
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005_investment_crm"
down_revision: Union[str, None] = "004_investment_agent_outputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_crm_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("investment_candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("contact_name", sa.String(200)),
        sa.Column("contact_channel", sa.String(50)),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("next_step", sa.Text()),
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "data_mode",
            sa.String(10),
            nullable=False,
            server_default="real",
        ),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "event_type IN "
            "('CONTACT', 'MEETING', 'NEGOTIATION', 'INTENT_SIGNED', "
            "'CONTRACT_SIGNED', 'SETTLED')",
            name="ck_investment_crm_event_type",
        ),
        sa.CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_investment_crm_event_data_mode",
        ),
    )
    op.create_index(
        "ix_investment_crm_event_candidate_id",
        "investment_crm_event",
        ["candidate_id"],
    )
    op.create_index(
        "ix_investment_crm_event_mode_type",
        "investment_crm_event",
        ["data_mode", "event_type"],
    )

    op.create_table(
        "investment_follow_up_task",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("investment_candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_id", sa.String(50), nullable=False),
        sa.Column("due_at", sa.DateTime()),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="MEDIUM",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="TODO",
        ),
        sa.Column("completion_note", sa.Text()),
        sa.Column(
            "data_mode",
            sa.String(10),
            nullable=False,
            server_default="real",
        ),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('TODO', 'IN_PROGRESS', 'DONE', 'CANCELLED')",
            name="ck_investment_follow_up_task_status",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_investment_follow_up_task_priority",
        ),
        sa.CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_investment_follow_up_task_data_mode",
        ),
    )
    op.create_index(
        "ix_investment_follow_up_task_candidate_id",
        "investment_follow_up_task",
        ["candidate_id"],
    )
    op.create_index(
        "ix_investment_follow_up_task_owner_status",
        "investment_follow_up_task",
        ["owner_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investment_follow_up_task_owner_status",
        table_name="investment_follow_up_task",
    )
    op.drop_index(
        "ix_investment_follow_up_task_candidate_id",
        table_name="investment_follow_up_task",
    )
    op.drop_table("investment_follow_up_task")
    op.drop_index(
        "ix_investment_crm_event_mode_type",
        table_name="investment_crm_event",
    )
    op.drop_index(
        "ix_investment_crm_event_candidate_id",
        table_name="investment_crm_event",
    )
    op.drop_table("investment_crm_event")
