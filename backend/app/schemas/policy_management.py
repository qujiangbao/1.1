"""Validated policy-condition management contracts."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ManagedPolicyCondition(BaseModel):
    condition_code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    field: str = Field(min_length=1, max_length=100)
    operator: Literal[
        "EXISTS",
        "EQ",
        "NE",
        "IN",
        "CONTAINS",
        "GTE",
        "GT",
        "LTE",
        "LT",
    ]
    expected_value: Any = None
    mandatory: bool = True
    review_status: Literal["DRAFT", "REVIEWED"] = "DRAFT"
    source_text: str | None = Field(default=None, max_length=4000)


class PolicyConditionsUpdate(BaseModel):
    conditions: list[ManagedPolicyCondition] = Field(max_length=100)


class ManagedPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    title: str
    level: str | None = None
    department: str | None = None
    category: str | None = None
    industry_scope: list[str] | None = None
    region_scope: list[str] | None = None
    publish_date: date | None = None
    expire_date: date | None = None
    status: str | None = None
    source: str | None = None
    eligibility_conditions: list[dict[str, Any]]
    conditions_reviewed_at: datetime | None = None
    conditions_reviewed_by: str | None = None
    eligibility_mode: Literal[
        "ELIGIBILITY",
        "REFERENCE_ONLY",
        "UNCLASSIFIED",
    ] = "UNCLASSIFIED"
    eligibility_mode_reason: str | None = None
