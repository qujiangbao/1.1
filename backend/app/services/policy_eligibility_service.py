"""Deterministic, condition-level policy eligibility evaluation.

Semantic retrieval only establishes relevance.  Eligibility is emitted only
when reviewed mandatory conditions are supported by enterprise evidence.
"""
from __future__ import annotations

from typing import Any

from app.schemas.enterprise import EnterpriseProfile
from app.schemas.investment_candidate import (
    PolicyConditionResult,
    PolicyEligibilityStatus,
)


SUPPORTED_FIELDS = {
    "region": "location",
    "location": "location",
    "industry": "industry",
    "company_type": "company_type",
    "enterprise_status": "enterprise_status",
    "established_date": "established_date",
    "capital_amount": "capital_amount",
    "patents_count": "patents_count",
    "employee_count": "employee_count",
    "funding_stage": "funding_stage",
    "credit_code": "credit_code",
}

DEMO_RULE_SOURCE_MARKERS = (
    "系统模板建议",
    "非政策原文",
    "通用示例规则",
    "粘贴政策原文中的对应申报条件",
)


def is_demo_policy_condition(requirement: dict[str, Any]) -> bool:
    """Identify legacy qualification templates that have no policy basis."""

    source_text = str(requirement.get("source_text") or "")
    return any(marker in source_text for marker in DEMO_RULE_SOURCE_MARKERS)


def is_reviewed_source_condition(requirement: dict[str, Any]) -> bool:
    """Return whether a rule may participate in eligibility matching."""

    return (
        str(requirement.get("review_status") or "").upper() == "REVIEWED"
        and bool(str(requirement.get("source_text") or "").strip())
        and not is_demo_policy_condition(requirement)
    )


def source_policy_conditions(
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove legacy demo rules from policy-management and Agent inputs."""

    return [
        requirement
        for requirement in requirements
        if isinstance(requirement, dict) and not is_demo_policy_condition(requirement)
    ]


def reviewed_source_policy_conditions(
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select only reviewed rules that quote the source policy text."""

    return [
        requirement
        for requirement in requirements
        if isinstance(requirement, dict) and is_reviewed_source_condition(requirement)
    ]


def _normal(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _compare(actual: Any, operator: str, expected: Any) -> bool | None:
    operator = operator.upper()
    if operator == "EXISTS":
        return actual not in (None, "", [], {})
    if actual in (None, "", [], {}):
        return None
    if operator == "EQ":
        return _normal(actual) == _normal(expected)
    if operator == "NE":
        return _normal(actual) != _normal(expected)
    if operator == "IN":
        values = expected if isinstance(expected, list) else [expected]
        actual_text = _normal(actual)
        return any(
            _normal(value) in actual_text or actual_text in _normal(value)
            for value in values
            if _normal(value)
        )
    if operator == "CONTAINS":
        values = expected if isinstance(expected, list) else [expected]
        actual_text = _normal(actual)
        return any(_normal(value) in actual_text for value in values)
    if operator in {"GTE", "GT", "LTE", "LT"}:
        try:
            actual_number = float(actual)
            expected_number = float(expected)
        except (TypeError, ValueError):
            return None
        if operator == "GTE":
            return actual_number >= expected_number
        if operator == "GT":
            return actual_number > expected_number
        if operator == "LTE":
            return actual_number <= expected_number
        return actual_number < expected_number
    return None


def evaluate_policy_conditions(
    profile: EnterpriseProfile,
    requirements: list[dict[str, Any]],
    *,
    enterprise_evidence_ids: list[str],
    policy_evidence_id: str,
) -> tuple[PolicyEligibilityStatus, list[PolicyConditionResult], str]:
    """Evaluate source-backed rules without comparing draft or demo rules."""

    requirements = source_policy_conditions(requirements)

    if not requirements:
        return (
            "RELATED",
            [],
            "政策与企业画像相关，但政策快照尚无结构化申报条件",
        )

    results: list[PolicyConditionResult] = []
    for index, requirement in enumerate(requirements, start=1):
        code = str(
            requirement.get("condition_code")
            or requirement.get("code")
            or f"CONDITION_{index}"
        )
        label = str(requirement.get("label") or code)
        field = str(requirement.get("field") or requirement.get("condition_type") or "")
        operator = str(requirement.get("operator") or "EQ").upper()
        expected = requirement.get("expected_value", requirement.get("value"))
        mandatory = bool(requirement.get("mandatory", True))
        source_text = requirement.get("source_text")
        profile_field = SUPPORTED_FIELDS.get(field)

        if not is_reviewed_source_condition(requirement):
            results.append(
                PolicyConditionResult(
                    condition_code=code,
                    label=label,
                    field=field,
                    operator=operator,
                    expected_value=expected,
                    actual_value=None,
                    status="NEEDS_MANUAL_REVIEW",
                    mandatory=mandatory,
                    reason="规则尚未引用政策原文并完成人工审核，不参与企业资格匹配",
                    source_text=source_text,
                    evidence_ids=[policy_evidence_id],
                    rule_review_status="DRAFT",
                )
            )
            continue

        if not profile_field or operator not in {
            "EXISTS",
            "EQ",
            "NE",
            "IN",
            "CONTAINS",
            "GTE",
            "GT",
            "LTE",
            "LT",
        }:
            results.append(
                PolicyConditionResult(
                    condition_code=code,
                    label=label,
                    field=field,
                    operator=operator,
                    expected_value=expected,
                    status="NEEDS_MANUAL_REVIEW",
                    mandatory=mandatory,
                    reason="该条件暂不支持自动核验",
                    source_text=source_text,
                    evidence_ids=[policy_evidence_id],
                    rule_review_status="REVIEWED",
                )
            )
            continue

        actual = getattr(profile, profile_field, None)
        comparison = _compare(actual, operator, expected)
        if comparison is None or not enterprise_evidence_ids:
            status = "UNKNOWN"
            reason = "企业字段或对应企业证据缺失"
            evidence_ids = [policy_evidence_id]
        elif comparison:
            status = "SATISFIED"
            reason = "结构化企业字段满足已复核政策条件"
            evidence_ids = [policy_evidence_id, *enterprise_evidence_ids]
        else:
            status = "UNSATISFIED"
            reason = "结构化企业字段不满足已复核政策条件"
            evidence_ids = [policy_evidence_id, *enterprise_evidence_ids]

        results.append(
            PolicyConditionResult(
                condition_code=code,
                label=label,
                field=field,
                operator=operator,
                expected_value=expected,
                actual_value=actual,
                status=status,
                mandatory=mandatory,
                reason=reason,
                source_text=source_text,
                evidence_ids=list(dict.fromkeys(evidence_ids)),
                rule_review_status="REVIEWED",
            )
        )

    mandatory_results = [
        item for item in results
        if item.mandatory and item.status != "NOT_APPLICABLE"
    ]
    if any(item.status == "UNSATISFIED" for item in mandatory_results):
        return "INELIGIBLE", results, "至少一项强制申报条件明确不满足"
    if mandatory_results and all(
        item.status == "SATISFIED" for item in mandatory_results
    ):
        return "ELIGIBLE", results, "全部已复核强制条件均有企业证据支持"
    if any(item.status == "SATISFIED" for item in mandatory_results):
        return (
            "POTENTIALLY_ELIGIBLE",
            results,
            "部分条件满足，其余条件仍需补证或人工复核",
        )
    return "UNKNOWN", results, "申报条件或企业字段不足，无法判断资格"
