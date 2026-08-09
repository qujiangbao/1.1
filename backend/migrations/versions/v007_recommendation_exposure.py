"""Add recommendation exposure events for unbiased offline learning.

Revision ID: 007_recommendation_exposure
Revises: 006_policy_conditions
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007_recommendation_exposure"
down_revision: Union[str, None] = "006_policy_conditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_exposure",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(36),
            sa.ForeignKey("investment_scenario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enterprise_id", sa.String(200), nullable=False),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column(
            "data_mode",
            sa.String(10),
            nullable=False,
            server_default="real",
        ),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "scenario_id",
            "enterprise_id",
            "user_id",
            "event_type",
            name="uq_recommendation_exposure_event",
        ),
        sa.CheckConstraint(
            "event_type IN ('IMPRESSION', 'SELECT')",
            name="ck_recommendation_exposure_event_type",
        ),
        sa.CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_recommendation_exposure_data_mode",
        ),
    )
    op.create_index(
        "ix_recommendation_exposure_scenario_id",
        "recommendation_exposure",
        ["scenario_id"],
    )
    op.create_index(
        "ix_recommendation_exposure_mode_created",
        "recommendation_exposure",
        ["data_mode", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_exposure_mode_created",
        table_name="recommendation_exposure",
    )
    op.drop_index(
        "ix_recommendation_exposure_scenario_id",
        table_name="recommendation_exposure",
    )
    op.drop_table("recommendation_exposure")
