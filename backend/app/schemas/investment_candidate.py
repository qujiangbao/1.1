"""Validated contracts for evidence-based investment recommendations."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


DataMode = Literal["real", "demo"]
CandidateStatus = Literal[
    "NEW",
    "REVIEWED",
    "CONTACTING",
    "NEGOTIATING",
    "REJECTED",
    "ARCHIVED",
]
RiskLevel = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
FeedbackDecision = Literal[
    "ACCEPT",
    "REJECT",
    "NEED_MORE_EVIDENCE",
    "DEFER",
]
AgentRunStatus = Literal["SUCCESS", "DATA_INSUFFICIENT", "FAILED"]
SignalStatus = Literal["AVAILABLE", "UNKNOWN", "NEEDS_VERIFICATION"]
PolicyEligibilityStatus = Literal[
    "RELATED",
    "POTENTIALLY_ELIGIBLE",
    "ELIGIBLE",
    "INELIGIBLE",
    "UNKNOWN",
]
PolicyConditionStatus = Literal[
    "SATISFIED",
    "UNSATISFIED",
    "UNKNOWN",
    "NEEDS_MANUAL_REVIEW",
    "NOT_APPLICABLE",
]
class EvidenceItem(BaseModel):
    id: str
    field: str
    claim: str
    value: Any = None
    source_type: str
    source_title: str
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime
    tool: str
    snapshot_id: str
    confidence: float = Field(ge=0, le=1)


class ScoreDimension(BaseModel):
    score: Optional[float] = Field(default=None, ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    reason: str
    evidence_ids: List[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    level: RiskLevel = "UNKNOWN"
    score: Optional[float] = Field(default=None, ge=0, le=100)
    reason: str
    evidence_ids: List[str] = Field(default_factory=list)


class PolicyConditionResult(BaseModel):
    condition_code: str
    label: str
    field: str
    operator: str
    expected_value: Any = None
    actual_value: Any = None
    status: PolicyConditionStatus
    mandatory: bool = True
    reason: str
    source_text: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    rule_review_status: Optional[Literal["DRAFT", "REVIEWED"]] = None


class PolicyMatch(BaseModel):
    policy_id: Optional[str] = None
    title: str
    match_type: PolicyEligibilityStatus = "RELATED"
    reason: str
    match_score: Optional[float] = Field(default=None, ge=0, le=100)
    matched_terms: List[str] = Field(default_factory=list)
    source_type: str = "public_policy"
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    condition_results: List[PolicyConditionResult] = Field(default_factory=list)


class AgentOutputEnvelope(BaseModel):
    """Enterprise-scoped, reviewable output from one business Agent.

    The envelope is persisted with the recommendation snapshot so the UI and
    later evaluations never have to reconstruct an Agent result from prose.
    """

    agent: str
    enterprise_id: Optional[str] = None
    status: AgentRunStatus
    result: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    unknown_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)
    run_ref: Optional[str] = None
    execution_time_ms: int = Field(default=0, ge=0)


class EnterpriseSignalItem(BaseModel):
    field: str
    value: Any = None
    status: SignalStatus
    evidence_ids: List[str] = Field(default_factory=list)
    as_of_date: Optional[datetime] = None
    confidence: float = Field(default=0, ge=0, le=1)
    note: Optional[str] = None


class RecommendationCard(BaseModel):
    enterprise_id: str
    enterprise_name: str
    industry_chain_role: Optional[str] = None
    overall_score: Optional[float] = Field(default=None, ge=0, le=100)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    data_status: Literal["READY", "DATA_INSUFFICIENT"]
    score_breakdown: Dict[str, ScoreDimension]
    risk: RiskAssessment
    policy_matches: List[PolicyMatch] = Field(default_factory=list)
    recommendation: str
    next_action: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    unknown_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    agent_outputs: Dict[str, AgentOutputEnvelope] = Field(default_factory=dict)
    trace_refs: Dict[str, str] = Field(default_factory=dict)
    data_mode: DataMode


class InvestmentDecisionRun(BaseModel):
    run_id: str
    version: str
    generated_at: datetime
    supervisor_output: AgentOutputEnvelope
    industry_output: AgentOutputEnvelope
    recommendations: List[RecommendationCard]
    warnings: List[str] = Field(default_factory=list)


class InvestmentScenarioCreate(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    industry: str = Field(min_length=1, max_length=200)
    target_chain_roles: List[str] = Field(min_length=1, max_length=10)
    location_preference: Optional[str] = Field(default="广州", max_length=200)
    limit: int = Field(default=5, ge=1, le=10)
    data_mode: DataMode = "real"
    weights: Optional[Dict[str, float]] = None

    @model_validator(mode="after")
    def validate_scoring_weights(self):
        if self.weights is None:
            return self
        expected = {
            "industry_fit",
            "technology",
            "growth",
            "landing_intent",
            "policy_fit",
            "data_completeness",
        }
        if set(self.weights) != expected:
            raise ValueError("weights must contain all six scoring dimensions")
        if any(value < 0.05 or value > 0.5 for value in self.weights.values()):
            raise ValueError("each scoring weight must be between 5% and 50%")
        if abs(sum(self.weights.values()) - 1.0) > 0.001:
            raise ValueError("scoring weights must total 100%")
        return self


class InvestmentScenarioCreated(BaseModel):
    scenario_id: str
    task_id: Optional[str] = None
    stream_url: Optional[str] = None
    status: str


class RecommendationResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    data_mode: DataMode
    generated_at: datetime
    version: str
    source_summary: Dict[str, Any]
    limitations: List[str]
    recommendations: List[RecommendationCard]


class CandidateCreate(BaseModel):
    scenario_id: str
    recommendation: RecommendationCard
    data_mode: DataMode


class CandidateUpdate(BaseModel):
    status: Optional[CandidateStatus] = None
    assignee_id: Optional[str] = Field(default=None, max_length=50)
    next_action: Optional[str] = Field(default=None, max_length=2000)
    manual_note: Optional[str] = Field(default=None, max_length=4000)


class CandidateFeedbackCreate(BaseModel):
    decision: FeedbackDecision
    reason_code: str = Field(min_length=1, max_length=100)
    comment: Optional[str] = Field(default=None, max_length=4000)


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    enterprise_id: str
    enterprise_name: str
    scenario_id: str
    industry_chain_role: Optional[str] = None
    overall_score: Optional[float] = None
    confidence: Optional[float] = None
    score_breakdown: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    unknown_fields: List[str]
    warnings: List[str]
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    trace_refs: Dict[str, str] = Field(default_factory=dict)
    risk_level: RiskLevel
    risk_summary: Optional[str] = None
    policy_matches: List[Dict[str, Any]]
    recommendation: str
    next_action: Optional[str] = None
    status: CandidateStatus
    assignee_id: Optional[str] = None
    source_task_id: Optional[str] = None
    data_mode: DataMode
    manual_note: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(BaseModel):
    items: List[CandidateRead]
    total: int
    limit: int
    offset: int
    next_cursor: Optional[str] = None
    data_mode: DataMode


class CandidateFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    decision: FeedbackDecision
    reason_code: str
    comment: Optional[str] = None
    reviewer_id: str
    created_at: datetime
