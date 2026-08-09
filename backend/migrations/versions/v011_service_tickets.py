"""Add enterprise service tickets.

Revision ID: 011_service_tickets
Revises: 010_remove_demo_conditions
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "011_service_tickets"
down_revision: Union[str, None] = "010_remove_demo_conditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_ticket",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("enterprise_id", sa.String(length=200)),
        sa.Column("enterprise_name", sa.String(length=500)),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="综合服务"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("assignee_id", sa.String(length=50)),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("resolution", sa.Text()),
        sa.Column("source_task_id", sa.String(length=50)),
        sa.Column("created_by", sa.String(length=50), nullable=False),
        sa.Column("updated_by", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'CLOSED')",
            name="ck_service_ticket_status",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_service_ticket_priority",
        ),
    )
    op.create_index("ix_service_ticket_status_updated", "service_ticket", ["status", "updated_at"])
    op.create_index("ix_service_ticket_enterprise", "service_ticket", ["enterprise_id"])


def downgrade() -> None:
    op.drop_index("ix_service_ticket_enterprise", table_name="service_ticket")
    op.drop_index("ix_service_ticket_status_updated", table_name="service_ticket")
    op.drop_table("service_ticket")
