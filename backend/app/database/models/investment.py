"""Investment decision-loop persistence models.

Recommendations remain a reviewable snapshot.  Only an explicit user action
creates an ``InvestmentCandidate``; model output is never promoted to a
business fact automatically.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database.session import Base


def _uuid() -> str:
    return str(uuid4())


class InvestmentScenario(Base):
    __tablename__ = "investment_scenario"
    __table_args__ = (
        CheckConstraint("data_mode IN ('real', 'demo')", name="ck_scenario_data_mode"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(300), nullable=False)
    industry = Column(String(200), nullable=False)
    target_chain_roles = Column(JSONB, nullable=False, default=list)
    location_preference = Column(String(200))
    result_limit = Column(Integer, nullable=False, default=5)
    data_mode = Column(String(10), nullable=False, default="real")
    status = Column(String(30), nullable=False, default="READY")
    recommendation_snapshot = Column(JSONB, nullable=False, default=list)
    snapshot_metadata = Column(JSONB, nullable=False, default=dict)
    source_task_id = Column(String(50))
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class InvestmentCandidate(Base):
    __tablename__ = "investment_candidate"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "scenario_id",
            "data_mode",
            name="uq_candidate_enterprise_scenario_mode",
        ),
        CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_candidate_data_mode",
        ),
        CheckConstraint(
            "risk_level IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')",
            name="ck_candidate_risk_level",
        ),
        CheckConstraint(
            "status IN "
            "('NEW', 'REVIEWED', 'CONTACTING', 'NEGOTIATING', "
            "'REJECTED', 'ARCHIVED')",
            name="ck_candidate_status",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    enterprise_id = Column(String(200), nullable=False)
    enterprise_name = Column(String(500), nullable=False)
    scenario_id = Column(
        String(36),
        ForeignKey("investment_scenario.id", ondelete="CASCADE"),
        nullable=False,
    )
    industry_chain_role = Column(String(200))
    overall_score = Column(Float)
    confidence = Column(Float)
    score_breakdown = Column(JSONB, nullable=False, default=dict)
    evidence = Column(JSONB, nullable=False, default=list)
    unknown_fields = Column(JSONB, nullable=False, default=list)
    warnings = Column(JSONB, nullable=False, default=list)
    agent_outputs = Column(JSONB, nullable=False, default=dict)
    trace_refs = Column(JSONB, nullable=False, default=dict)
    risk_level = Column(String(20), nullable=False, default="UNKNOWN")
    risk_summary = Column(Text)
    policy_matches = Column(JSONB, nullable=False, default=list)
    recommendation = Column(Text, nullable=False)
    next_action = Column(Text)
    status = Column(String(30), nullable=False, default="NEW")
    assignee_id = Column(String(50))
    source_task_id = Column(String(50))
    data_mode = Column(String(10), nullable=False, default="real")
    manual_note = Column(Text)
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class CandidateFeedback(Base):
    __tablename__ = "candidate_feedback"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('ACCEPT', 'REJECT', 'NEED_MORE_EVIDENCE', 'DEFER')",
            name="ck_candidate_feedback_decision",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    candidate_id = Column(
        String(36),
        ForeignKey("investment_candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision = Column(String(30), nullable=False)
    reason_code = Column(String(100), nullable=False)
    comment = Column(Text)
    reviewer_id = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class CandidateAudit(Base):
    __tablename__ = "candidate_audit"

    id = Column(String(36), primary_key=True, default=_uuid)
    candidate_id = Column(
        String(36),
        ForeignKey("investment_candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(50), nullable=False)
    actor_id = Column(String(50), nullable=False)
    changes = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class InvestmentCRMEvent(Base):
    """An immutable, user-recorded business event for one candidate."""

    __tablename__ = "investment_crm_event"
    __table_args__ = (
        CheckConstraint(
            "event_type IN "
            "('CONTACT', 'MEETING', 'NEGOTIATION', 'INTENT_SIGNED', "
            "'CONTRACT_SIGNED', 'SETTLED')",
            name="ck_investment_crm_event_type",
        ),
        CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_investment_crm_event_data_mode",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    candidate_id = Column(
        String(36),
        ForeignKey("investment_candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(30), nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    contact_name = Column(String(200))
    contact_channel = Column(String(50))
    summary = Column(Text, nullable=False)
    next_step = Column(Text)
    evidence_refs = Column(JSONB, nullable=False, default=list)
    data_mode = Column(String(10), nullable=False, default="real")
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class InvestmentFollowUpTask(Base):
    """A reviewable follow-up obligation linked to a candidate."""

    __tablename__ = "investment_follow_up_task"
    __table_args__ = (
        CheckConstraint(
            "status IN ('TODO', 'IN_PROGRESS', 'DONE', 'CANCELLED')",
            name="ck_investment_follow_up_task_status",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_investment_follow_up_task_priority",
        ),
        CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_investment_follow_up_task_data_mode",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    candidate_id = Column(
        String(36),
        ForeignKey("investment_candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(300), nullable=False)
    description = Column(Text)
    owner_id = Column(String(50), nullable=False)
    due_at = Column(DateTime)
    priority = Column(String(20), nullable=False, default="MEDIUM")
    status = Column(String(20), nullable=False, default="TODO")
    completion_note = Column(Text)
    data_mode = Column(String(10), nullable=False, default="real")
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class RecommendationExposure(Base):
    """An idempotent impression/selection event used for offline evaluation."""

    __tablename__ = "recommendation_exposure"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "enterprise_id",
            "user_id",
            "event_type",
            name="uq_recommendation_exposure_event",
        ),
        CheckConstraint(
            "event_type IN ('IMPRESSION', 'SELECT')",
            name="ck_recommendation_exposure_event_type",
        ),
        CheckConstraint(
            "data_mode IN ('real', 'demo')",
            name="ck_recommendation_exposure_data_mode",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    scenario_id = Column(
        String(36),
        ForeignKey("investment_scenario.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enterprise_id = Column(String(200), nullable=False)
    user_id = Column(String(50), nullable=False)
    event_type = Column(String(20), nullable=False)
    position = Column(Integer, nullable=False)
    score = Column(Float)
    data_mode = Column(String(10), nullable=False, default="real")
    context = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
