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
    allow_draft_preview: bool = False,
) -> tuple[PolicyEligibilityStatus, list[PolicyConditionResult], str]:
    """Evaluate conditions and optionally expose a non-authoritative preview.

    Draft comparisons never become a confirmed eligibility decision.  The
    preview is used by the policy management screen so newly imported
    enterprise evidence can participate immediately while the policy rule is
    still waiting for an administrator to verify it against the source text.
    """

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
        review_status = str(requirement.get("review_status") or "").upper()
        profile_field = SUPPORTED_FIELDS.get(field)

        if review_status != "REVIEWED":
            actual = getattr(profile, profile_field, None) if profile_field else None
            comparison = (
                _compare(actual, operator, expected)
                if profile_field and operator in {
                    "EXISTS", "EQ", "NE", "IN", "CONTAINS",
                    "GTE", "GT", "LTE", "LT",
                }
                else None
            )
            preview_status = (
                "SATISFIED"
                if comparison is True and enterprise_evidence_ids
                else "UNSATISFIED"
                if comparison is False and enterprise_evidence_ids
                else "UNKNOWN"
            )
            if allow_draft_preview and preview_status == "SATISFIED":
                reason = "自动预匹配：企业字段满足待复核规则；规则确认前不作为正式资格结论"
            elif allow_draft_preview and preview_status == "UNSATISFIED":
                reason = "自动预匹配：企业字段不满足待复核规则；规则确认前不作为正式排除结论"
            elif allow_draft_preview:
                reason = "自动预匹配缺少企业字段或证据，且政策规则仍待人工复核"
            else:
                reason = "政策条件尚未经过人工复核"
            results.append(
                PolicyConditionResult(
                    condition_code=code,
                    label=label,
                    field=field,
                    operator=operator,
                    expected_value=expected,
                    actual_value=actual,
                    status="NEEDS_MANUAL_REVIEW",
                    mandatory=mandatory,
                    reason=reason,
                    source_text=source_text,
                    evidence_ids=list(dict.fromkeys([
                        policy_evidence_id,
                        *(enterprise_evidence_ids if comparison is not None else []),
                    ])),
                    rule_review_status="DRAFT",
                    preview_status=preview_status,
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
                    preview_status="UNKNOWN",
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
    if allow_draft_preview:
        if any(
            item.rule_review_status == "DRAFT"
            and item.preview_status == "UNSATISFIED"
            for item in mandatory_results
        ):
            return (
                "UNKNOWN",
                results,
                "按待复核规则自动预匹配为初步不符合；规则确认前不作正式排除",
            )
        if mandatory_results and all(
            item.status == "SATISFIED"
            or (
                item.rule_review_status == "DRAFT"
                and item.preview_status == "SATISFIED"
            )
            for item in mandatory_results
        ):
            return (
                "POTENTIALLY_ELIGIBLE",
                results,
                "自动预匹配满足全部现有条件；待政策规则复核后可确认资格",
            )
        if any(
            item.status == "SATISFIED" or item.preview_status == "SATISFIED"
            for item in mandatory_results
        ):
            return (
                "POTENTIALLY_ELIGIBLE",
                results,
                "自动预匹配满足部分条件，其余条件需要补充企业证据或复核规则",
            )
    if any(item.status == "SATISFIED" for item in mandatory_results):
        return (
            "POTENTIALLY_ELIGIBLE",
            results,
            "部分条件满足，其余条件仍需补证或人工复核",
        )
    return "UNKNOWN", results, "申报条件或企业字段不足，无法判断资格"
