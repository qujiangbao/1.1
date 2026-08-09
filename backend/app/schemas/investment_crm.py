"""Contracts for persisted investment CRM activity and follow-up work."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.investment_candidate import DataMode


CRMEventType = Literal[
    "CONTACT",
    "MEETING",
    "NEGOTIATION",
    "INTENT_SIGNED",
    "CONTRACT_SIGNED",
    "SETTLED",
]
TaskStatus = Literal["TODO", "IN_PROGRESS", "DONE", "CANCELLED"]
TaskPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]


class CRMEventCreate(BaseModel):
    candidate_id: str
    event_type: CRMEventType
    occurred_at: datetime
    contact_name: str | None = Field(default=None, max_length=200)
    contact_channel: str | None = Field(default=None, max_length=50)
    summary: str = Field(min_length=1, max_length=4000)
    next_step: str | None = Field(default=None, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    data_mode: DataMode


class CRMEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    event_type: CRMEventType
    occurred_at: datetime
    contact_name: str | None = None
    contact_channel: str | None = None
    summary: str
    next_step: str | None = None
    evidence_refs: list[str]
    data_mode: DataMode
    created_by: str
    created_at: datetime


class FollowUpTaskCreate(BaseModel):
    candidate_id: str
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    owner_id: str = Field(min_length=1, max_length=50)
    due_at: datetime | None = None
    priority: TaskPriority = "MEDIUM"
    data_mode: DataMode


class FollowUpTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    owner_id: str | None = Field(default=None, min_length=1, max_length=50)
    due_at: datetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    completion_note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_completion_note(self):
        if self.status == "DONE" and not (self.completion_note or "").strip():
            raise ValueError("completion_note is required when status is DONE")
        return self


class FollowUpTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    title: str
    description: str | None = None
    owner_id: str
    due_at: datetime | None = None
    priority: TaskPriority
    status: TaskStatus
    completion_note: str | None = None
    data_mode: DataMode
    created_by: str
    created_at: datetime
    updated_at: datetime


class FunnelStage(BaseModel):
    stage: Literal[
        "TARGET",
        "CONTACT",
        "NEGOTIATION",
        "SIGNED",
        "SETTLED",
    ]
    label: str
    count: int = Field(ge=0)


class InvestmentFunnelRead(BaseModel):
    data_mode: DataMode
    source: Literal["investment_crm_event"]
    generated_at: datetime
    stages: list[FunnelStage]


class RecommendationExposureItem(BaseModel):
    enterprise_id: str
    position: int = Field(ge=1, le=100)
    score: float | None = Field(default=None, ge=0, le=100)


class RecommendationExposureCreate(BaseModel):
    event_type: Literal["IMPRESSION", "SELECT"]
    data_mode: DataMode
    items: list[RecommendationExposureItem] = Field(min_length=1, max_length=100)
    context: dict = Field(default_factory=dict)
