"""Add managed policy eligibility conditions.

Revision ID: 006_policy_conditions
Revises: 005_investment_crm
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006_policy_conditions"
down_revision: Union[str, None] = "005_investment_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy",
        sa.Column(
            "eligibility_conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "policy",
        sa.Column("conditions_reviewed_at", sa.DateTime()),
    )
    op.add_column(
        "policy",
        sa.Column("conditions_reviewed_by", sa.String(50)),
    )


def downgrade() -> None:
    op.drop_column("policy", "conditions_reviewed_by")
    op.drop_column("policy", "conditions_reviewed_at")
    op.drop_column("policy", "eligibility_conditions")
