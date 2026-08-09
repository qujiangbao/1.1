"""Add indexes for dashboard, risk, policy, and conversation hot paths.

Revision ID: 009_business_indexes
Revises: 008_policy_crawler
"""

from typing import Union

from alembic import op


revision: str = "009_business_indexes"
down_revision: Union[str, None] = "008_policy_crawler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_enterprise_industry_id",
        "enterprise",
        ["industry_id"],
    )
    op.create_index(
        "ix_policy_publish_date",
        "policy",
        ["publish_date"],
    )
    op.create_index(
        "ix_risk_enterprise_created",
        "risk",
        ["enterprise_id", "created_time", "risk_id"],
    )
    op.create_index(
        "ix_risk_created_time",
        "risk",
        ["created_time"],
    )
    op.execute(
        "CREATE INDEX ix_risk_upper_level ON risk (upper(risk_level))"
    )
    op.create_index(
        "ix_agent_execution_end_time",
        "agent_execution",
        ["end_time"],
    )
    op.create_index(
        "ix_agent_memory_conversation_created",
        "agent_memory",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_agent_task_user_id",
        "agent_task",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_task_user_id", table_name="agent_task")
    op.drop_index(
        "ix_agent_memory_conversation_created",
        table_name="agent_memory",
    )
    op.drop_index("ix_agent_execution_end_time", table_name="agent_execution")
    op.drop_index("ix_risk_upper_level", table_name="risk")
    op.drop_index("ix_risk_created_time", table_name="risk")
    op.drop_index("ix_risk_enterprise_created", table_name="risk")
    op.drop_index("ix_policy_publish_date", table_name="policy")
    op.drop_index("ix_enterprise_industry_id", table_name="enterprise")
