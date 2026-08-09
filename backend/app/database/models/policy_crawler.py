"""Persistent policy-crawler access, approval and run audit models."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.database.session import Base


class PolicyCrawlerAccessRequest(Base):
    __tablename__ = "policy_crawler_access_requests"

    request_id = Column(String(36), primary_key=True)
    requester_id = Column(
        String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    reason = Column(Text)
    status = Column(String(20), nullable=False, default="PENDING")
    decided_by = Column(String(50), ForeignKey("users.user_id"))
    decision_note = Column(Text)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    decided_at = Column(DateTime)


class PolicyCrawlerGrant(Base):
    __tablename__ = "policy_crawler_grants"

    user_id = Column(
        String(50), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    status = Column(String(20), nullable=False, default="APPROVED")
    approved_by = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    approved_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_by = Column(String(50), ForeignKey("users.user_id"))
    revoked_at = Column(DateTime)


class PolicyCrawlRun(Base):
    __tablename__ = "policy_crawl_runs"

    run_id = Column(String(36), primary_key=True)
    requested_by = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    status = Column(String(20), nullable=False, default="QUEUED")
    pages = Column(Integer, nullable=False, default=3)
    workers = Column(Integer, nullable=False, default=3)
    force = Column(Boolean, nullable=False, default=False)
    stats = Column(JSONB, nullable=False, default=dict)
    error = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
