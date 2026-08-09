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


router = APIRouter()
WRITE_ROLES = ("super_admin", "park_manager", "policy_manager")


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
                ManagedPolicyRead.model_validate(item).model_dump(mode="json")
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
    policy.eligibility_conditions = conditions
    policy.conditions_reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    policy.conditions_reviewed_by = user.user_id

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
            "conditions_reviewed_at": policy.conditions_reviewed_at.isoformat(),
            "conditions_reviewed_by": user.user_id,
        }
    await session.commit()
    await session.refresh(policy)
    return {
        "success": True,
        "data": ManagedPolicyRead.model_validate(policy).model_dump(mode="json"),
        "updated_chunks": len(chunks),
    }


@router.get("/policy-management/policies/{policy_id}/candidate-eligibility")
async def list_policy_candidate_eligibility(
    policy_id: str,
    data_mode: str = Query(default="real", pattern="^(real|demo)$"),
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    """Reverse lookup: which current candidates qualify for one policy, and why."""

    policy = await session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    rows = list(
        (
            await session.execute(
                select(InvestmentCandidate)
                .where(
                    InvestmentCandidate.data_mode == data_mode,
                    InvestmentCandidate.status.notin_(["REJECTED", "ARCHIVED"]),
                )
                .order_by(InvestmentCandidate.updated_at.desc())
            )
        ).scalars().all()
    )
    # One enterprise can be added from multiple scenarios. The newest candidate
    # snapshot is the current scope and avoids duplicate enterprise names.
    candidates: dict[str, InvestmentCandidate] = {}
    for candidate in rows:
        candidates.setdefault(candidate.enterprise_id, candidate)

    conditions = [
        item for item in (policy.eligibility_conditions or [])
        if isinstance(item, dict)
    ]
    items = []
    from app.tools.enterprise_data import get_enterprise_data_tool

    enterprise_tool = get_enterprise_data_tool()
    for candidate in candidates.values():
        relevance_match = _stored_policy_match(candidate, policy_id)
        if relevance_match is None:
            continue
        try:
            profile = await enterprise_tool.get_profile(candidate.enterprise_id)
            items.append(
                _candidate_eligibility_item(
                    candidate,
                    profile,
                    policy_id,
                    conditions,
                    relevance_match,
                )
            )
        except KeyError:
            items.append({
                "candidate_id": candidate.id,
                "enterprise_id": candidate.enterprise_id,
                "enterprise_name": candidate.enterprise_name,
                "candidate_status": candidate.status,
                "match_type": "UNKNOWN",
                "reason": "企业公开快照已不存在，无法重新核验",
                "match_score": relevance_match.get("match_score"),
                "matched_terms": relevance_match.get("matched_terms") or [],
                "condition_results": [],
                "evaluated_at": (
                    candidate.updated_at.isoformat() if candidate.updated_at else None
                ),
            })

    rank = {
        "ELIGIBLE": 0,
        "POTENTIALLY_ELIGIBLE": 1,
        "UNKNOWN": 2,
        "RELATED": 2,
        "INELIGIBLE": 3,
    }
    items.sort(key=lambda item: (rank.get(item["match_type"], 9), item["enterprise_name"]))
    return {
        "success": True,
        "data": {
            "policy_id": policy.policy_id,
            "policy_title": policy.title,
            "data_mode": data_mode,
            "scope": "investment_candidate_pool",
            "scope_candidate_count": len(candidates),
            "relevant_candidate_count": len(items),
            "eligible_count": sum(item["match_type"] == "ELIGIBLE" for item in items),
            "potential_count": sum(
                item["match_type"] in {"POTENTIALLY_ELIGIBLE", "UNKNOWN", "RELATED"}
                for item in items
            ),
            "ineligible_count": sum(item["match_type"] == "INELIGIBLE" for item in items),
            "condition_count": len(conditions),
            "reviewed_condition_count": sum(
                str(item.get("review_status") or "").upper() == "REVIEWED"
                for item in conditions
            ),
            "conditions_origin": policy.conditions_reviewed_by,
            "items": items,
        },
    }
