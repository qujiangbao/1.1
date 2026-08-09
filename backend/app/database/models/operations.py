"""Persistent park-operation records."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Index, String, Text

from app.database.session import Base


class ServiceTicket(Base):
    __tablename__ = "service_ticket"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'CLOSED')",
            name="ck_service_ticket_status",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_service_ticket_priority",
        ),
        Index("ix_service_ticket_status_updated", "status", "updated_at"),
        Index("ix_service_ticket_enterprise", "enterprise_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id = Column(String(200))
    enterprise_name = Column(String(500))
    subject = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, default="综合服务")
    priority = Column(String(20), nullable=False, default="MEDIUM")
    status = Column(String(20), nullable=False, default="OPEN")
    assignee_id = Column(String(50))
    due_at = Column(DateTime)
    resolution = Column(Text)
    source_task_id = Column(String(50))
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
