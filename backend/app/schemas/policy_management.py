"""Validated policy-condition management contracts."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DISALLOWED_POLICY_SOURCE_MARKERS = (
    "系统模板建议",
    "非政策原文",
    "通用示例规则",
    "粘贴政策原文中的对应申报条件",
)


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

    @model_validator(mode="after")
    def validate_policy_source(self):
        source_text = (self.source_text or "").strip()
        if any(marker in source_text for marker in DISALLOWED_POLICY_SOURCE_MARKERS):
            raise ValueError("资格规则不得使用系统模板或非政策原文作为依据")
        if self.review_status == "REVIEWED" and not source_text:
            raise ValueError("审核通过的资格规则必须填写对应政策原文")
        return self


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
