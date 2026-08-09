"""Persist enterprise-scoped Agent outputs with investment candidates.

Revision ID: 004_investment_agent_outputs
Revises: 003_investment_candidate
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "004_investment_agent_outputs"
down_revision: Union[str, None] = "003_investment_candidate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "investment_candidate",
        sa.Column(
            "agent_outputs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "investment_candidate",
        sa.Column(
            "trace_refs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("investment_candidate", "trace_refs")
    op.drop_column("investment_candidate", "agent_outputs")
