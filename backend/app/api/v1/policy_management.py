"""Policy catalog and reviewed eligibility-condition management."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.investment import investment_db
from app.core.permissions import require_any_role
from app.core.security import UserContext, require_user
from app.database.models.business import Policy, PolicyChunk
from app.database.models.investment import InvestmentCandidate
from app.schemas.policy_management import (
    ManagedPolicyRead,
    PolicyConditionsUpdate,
)
from app.services.policy_applicability_service import classify_policy_applicability
from app.services.policy_eligibility_service import (
    reviewed_source_policy_conditions,
    source_policy_conditions,
)
from app.services.policy_condition_extractor import extract_policy_condition_drafts


router = APIRouter()
WRITE_ROLES = ("super_admin", "park_manager", "policy_manager")


def _managed_policy_dump(policy: Policy) -> dict:
    payload = ManagedPolicyRead.model_validate(policy).model_dump(mode="json")
    payload["eligibility_conditions"] = source_policy_conditions(
        payload["eligibility_conditions"]
    )
    if policy.conditions_reviewed_by in {"template_suggestion", "seed_policy_conditions"}:
        payload["conditions_reviewed_at"] = None
        payload["conditions_reviewed_by"] = None
    mode, reason = classify_policy_applicability(policy)
    payload["eligibility_mode"] = mode
    payload["eligibility_mode_reason"] = reason
    return payload


def _stored_policy_match(candidate: InvestmentCandidate, policy_id: str) -> dict | None:
    for match in candidate.policy_matches or []:
        if str(match.get("policy_id") or "") == policy_id:
            return match
    return None


def _candidate_eligibility_item(
    candidate: InvestmentCandidate,
    profile,
    policy_id: str,
    conditions: list[dict],
    relevance_match: dict,
) -> dict:
    from app.services.policy_eligibility_service import evaluate_policy_conditions

    evidence_ids = [
        str(item.get("id"))
        for item in (candidate.evidence or [])
        if isinstance(item, dict) and item.get("id")
    ]
    match_type, condition_results, reason = evaluate_policy_conditions(
        profile,
        conditions,
        enterprise_evidence_ids=evidence_ids,
        policy_evidence_id=f"policy-{policy_id}",
    )
    return {
        "candidate_id": candidate.id,
        "enterprise_id": candidate.enterprise_id,
        "enterprise_name": candidate.enterprise_name,
        "candidate_status": candidate.status,
        "match_type": match_type,
        "reason": reason,
        "match_score": relevance_match.get("match_score"),
        "matched_terms": relevance_match.get("matched_terms") or [],
        "condition_results": [
            result.model_dump(mode="json") for result in condition_results
        ],
        "evaluated_at": (
            candidate.updated_at.isoformat() if candidate.updated_at else None
        ),
    }


def _enterprise_eligibility_item(
    profile,
    policy_id: str,
    conditions: list[dict],
) -> dict:
    """Evaluate one enterprise from the full park catalog for one policy."""

    from app.services.policy_eligibility_service import evaluate_policy_conditions

    enterprise_evidence_ids = [
        f"enterprise-{profile.enterprise_id}-{index}"
        for index, evidence in enumerate(profile.evidence or [], start=1)
        if isinstance(evidence, dict)
        and (evidence.get("value") or evidence.get("url") or evidence.get("document_id"))
    ]
    match_type, condition_results, reason = evaluate_policy_conditions(
        profile,
        conditions,
        enterprise_evidence_ids=enterprise_evidence_ids,
        policy_evidence_id=f"policy-{policy_id}",
    )
    mandatory = [item for item in condition_results if item.mandatory]
    positive = [
        item for item in mandatory
        if item.status == "SATISFIED"
    ]
    known = [
        item for item in mandatory
        if item.status in {"SATISFIED", "UNSATISFIED"}
    ]
    if match_type == "ELIGIBLE":
        preliminary_outcome = "MATCH"
        decision_basis = "CONFIRMED"
    elif match_type == "INELIGIBLE":
        preliminary_outcome = "NO_MATCH"
        decision_basis = "CONFIRMED"
    elif match_type == "POTENTIALLY_ELIGIBLE":
        preliminary_outcome = "MATCH"
        decision_basis = "PRELIMINARY"
    else:
        preliminary_outcome = "INSUFFICIENT"
        decision_basis = "INSUFFICIENT"

    return {
        "candidate_id": None,
        "enterprise_id": profile.enterprise_id,
        "enterprise_name": profile.name,
        "candidate_status": None,
        "match_type": match_type,
        "preliminary_outcome": preliminary_outcome,
        "decision_basis": decision_basis,
        "reason": reason,
        "match_score": round(len(positive) / len(mandatory) * 100, 1) if mandatory else None,
        "matched_terms": [item.label for item in positive],
        "condition_results": [
            result.model_dump(mode="json") for result in condition_results
        ],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": profile.data_source,
        "evidence_count": len(enterprise_evidence_ids),
        "known_condition_count": len(known),
    }


@router.get("/policy-management/policies")
async def list_managed_policies(
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    filters = []
    if q:
        token = f"%{q.strip()}%"
        filters.append(
            or_(
                Policy.title.ilike(token),
                Policy.department.ilike(token),
                Policy.policy_id.ilike(token),
            )
        )
    total = int(
        (
            await session.execute(
                select(func.count(Policy.policy_id)).where(*filters)
            )
        ).scalar()
        or 0
    )
    policies = list(
        (
            await session.execute(
                select(Policy)
                .where(*filters)
                .order_by(
                    Policy.publish_date.desc().nullslast(),
                    Policy.policy_id,
                )
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
    )
    return {
        "success": True,
        "data": {
            "items": [
                _managed_policy_dump(item)
                for item in policies
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.patch("/policy-management/policies/{policy_id}/conditions")
async def update_policy_conditions(
    policy_id: str,
    body: PolicyConditionsUpdate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    policy = await session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    conditions = [
        condition.model_dump(mode="json")
        for condition in body.conditions
    ]
    reviewed_conditions = reviewed_source_policy_conditions(conditions)
    reviewed_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        if reviewed_conditions
        else None
    )
    policy.eligibility_conditions = conditions
    policy.conditions_reviewed_at = reviewed_at
    policy.conditions_reviewed_by = user.user_id if reviewed_conditions else None

    chunks = list(
        (
            await session.execute(
                select(PolicyChunk).where(PolicyChunk.policy_id == policy_id)
            )
        ).scalars().all()
    )
    for chunk in chunks:
        chunk.metadata_ = {
            **(chunk.metadata_ or {}),
            "requirements": conditions,
            "conditions_reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
            "conditions_reviewed_by": user.user_id if reviewed_conditions else None,
        }
    await session.commit()
    await session.refresh(policy)
    return {
        "success": True,
        "data": _managed_policy_dump(policy),
        "updated_chunks": len(chunks),
    }


@router.post("/policy-management/policies/{policy_id}/conditions/extract")
async def extract_policy_conditions(
    policy_id: str,
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    """Extract source-backed drafts; never mark them reviewed automatically."""
    policy = await session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    drafts = extract_policy_condition_drafts(policy.content or "")
    existing = source_policy_conditions([
        item for item in (policy.eligibility_conditions or [])
        if isinstance(item, dict)
    ])
    reviewed = reviewed_source_policy_conditions(existing)
    conditions = [*reviewed, *drafts]
    policy.eligibility_conditions = conditions
    policy.conditions_reviewed_at = (
        policy.conditions_reviewed_at if reviewed else None
    )
    policy.conditions_reviewed_by = (
        policy.conditions_reviewed_by if reviewed else None
    )
    chunks = list((await session.execute(
        select(PolicyChunk).where(PolicyChunk.policy_id == policy_id)
    )).scalars().all())
    for chunk in chunks:
        chunk.metadata_ = {
            **(chunk.metadata_ or {}),
            "requirements": conditions,
            "condition_extraction": "source_text_deterministic_v1",
        }
    await session.commit()
    await session.refresh(policy)
    return {
        "success": True,
        "data": _managed_policy_dump(policy),
        "extracted_count": len(drafts),
        "preserved_reviewed_count": len(reviewed),
        "updated_chunks": len(chunks),
    }


@router.get("/policy-management/policies/{policy_id}/candidate-eligibility")
async def list_policy_candidate_eligibility(
    policy_id: str,
    data_mode: str = Query(default="real", pattern="^real$"),
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    """Match reviewed, source-backed rules against the real enterprise catalog."""

    policy = await session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    stored_conditions = [
        item for item in (policy.eligibility_conditions or [])
        if isinstance(item, dict)
    ]
    source_conditions = source_policy_conditions(stored_conditions)
    conditions = reviewed_source_policy_conditions(source_conditions)
    applicability_mode, applicability_reason = classify_policy_applicability(policy)
    if applicability_mode != "ELIGIBILITY" or not conditions:
        unavailable_reason = (
            applicability_reason
            if applicability_mode != "ELIGIBILITY"
            else "尚无引用政策原文并经人工审核的资格规则，未执行企业匹配"
        )
        return {
            "success": True,
            "data": {
                "policy_id": policy.policy_id,
                "policy_title": policy.title,
                "data_mode": data_mode,
                "scope": "park_enterprise_catalog",
                "scope_enterprise_count": 0,
                "evaluated_enterprise_count": 0,
                "relevant_enterprise_count": 0,
                "eligible_count": 0,
                "potential_count": 0,
                "ineligible_count": 0,
                "insufficient_count": 0,
                "condition_count": len(source_conditions),
                "reviewed_condition_count": len(conditions),
                "conditions_origin": policy.conditions_reviewed_by,
                "match_supported": False,
                "applicability_mode": applicability_mode,
                "applicability_reason": applicability_reason,
                "match_unavailable_reason": unavailable_reason,
                "items": [],
            },
        }

    from app.tools.enterprise_data import get_enterprise_data_tool

    enterprise_tool = get_enterprise_data_tool()
    catalog = await enterprise_tool.search_enterprises("", limit=5000)
    items = [
        _enterprise_eligibility_item(profile, policy_id, conditions)
        for profile in catalog.enterprises
    ]

    rank = {
        "ELIGIBLE": 0,
        "POTENTIALLY_ELIGIBLE": 1,
        "UNKNOWN": 2,
        "RELATED": 2,
        "INELIGIBLE": 3,
    }
    items.sort(key=lambda item: (
        rank.get(item["match_type"], 9),
        0 if item["preliminary_outcome"] == "MATCH" else 1,
        -(item.get("match_score") or 0),
        item["enterprise_name"],
    ))
    insufficient_count = sum(
        item["preliminary_outcome"] == "INSUFFICIENT" for item in items
    )
    return {
        "success": True,
        "data": {
            "policy_id": policy.policy_id,
            "policy_title": policy.title,
            "data_mode": data_mode,
            "scope": "park_enterprise_catalog",
            "scope_enterprise_count": catalog.total,
            "evaluated_enterprise_count": len(items),
            "relevant_enterprise_count": len(items),
            "eligible_count": sum(item["match_type"] == "ELIGIBLE" for item in items),
            "potential_count": sum(
                item["match_type"] == "POTENTIALLY_ELIGIBLE"
                for item in items
            ),
            "ineligible_count": sum(item["match_type"] == "INELIGIBLE" for item in items),
            "insufficient_count": insufficient_count,
            "condition_count": len(source_conditions),
            "reviewed_condition_count": len(conditions),
            "conditions_origin": policy.conditions_reviewed_by,
            "match_supported": True,
            "applicability_mode": applicability_mode,
            "applicability_reason": applicability_reason,
            "match_unavailable_reason": None,
            "items": items,
        },
    }
