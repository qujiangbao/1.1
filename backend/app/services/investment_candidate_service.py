"""Candidate-pool write boundary, state transitions, feedback and audit."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.investment import (
    CandidateAudit,
    CandidateFeedback,
    InvestmentCandidate,
    InvestmentScenario,
)
from app.schemas.investment_candidate import (
    CandidateCreate,
    CandidateFeedbackCreate,
    CandidateListResponse,
    CandidateRead,
    CandidateUpdate,
    RecommendationCard,
)


ALLOWED_TRANSITIONS = {
    "NEW": {"REVIEWED", "CONTACTING", "REJECTED", "ARCHIVED"},
    "REVIEWED": {"CONTACTING", "REJECTED", "ARCHIVED"},
    "CONTACTING": {"REVIEWED", "NEGOTIATING", "REJECTED", "ARCHIVED"},
    "NEGOTIATING": {"REVIEWED", "REJECTED", "ARCHIVED"},
    "REJECTED": {"REVIEWED", "ARCHIVED"},
    "ARCHIVED": {"REVIEWED"},
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _scenario(
    session: AsyncSession,
    scenario_id: str,
) -> InvestmentScenario:
    scenario = await session.get(InvestmentScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Investment scenario not found")
    return scenario


def _snapshot_card(
    scenario: InvestmentScenario,
    enterprise_id: str,
) -> RecommendationCard:
    for raw in scenario.recommendation_snapshot or []:
        if raw.get("enterprise_id") == enterprise_id:
            return RecommendationCard.model_validate(raw)
    raise HTTPException(
        status_code=422,
        detail="Recommendation is not part of this scenario snapshot",
    )


async def _verify_enterprise(card: RecommendationCard) -> None:
    if card.data_mode == "demo":
        if not card.enterprise_id.startswith("DEMO-"):
            raise HTTPException(
                status_code=422,
                detail="Demo candidates must come from the isolated demo scenario",
            )
        return

    from app.tools.enterprise_data import get_enterprise_data_tool

    try:
        profile = await get_enterprise_data_tool().get_profile(card.enterprise_id)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="Enterprise no longer exists") from exc
    if profile.name != card.enterprise_name:
        raise HTTPException(
            status_code=409,
            detail="Enterprise snapshot identity changed; regenerate recommendations",
        )


async def create_candidate(
    session: AsyncSession,
    body: CandidateCreate,
    *,
    user_id: str,
) -> tuple[InvestmentCandidate, bool]:
    scenario = await _scenario(session, body.scenario_id)
    if scenario.data_mode != body.data_mode:
        raise HTTPException(
            status_code=422,
            detail="Scenario and candidate data_mode must match",
        )
    if body.recommendation.data_mode != body.data_mode:
        raise HTTPException(
            status_code=422,
            detail="Recommendation and candidate data_mode must match",
        )

    card = _snapshot_card(scenario, body.recommendation.enterprise_id)
    await _verify_enterprise(card)

    existing = await session.execute(
        select(InvestmentCandidate).where(
            InvestmentCandidate.enterprise_id == card.enterprise_id,
            InvestmentCandidate.scenario_id == scenario.id,
            InvestmentCandidate.data_mode == body.data_mode,
        )
    )
    candidate = existing.scalar_one_or_none()
    if candidate is not None:
        return candidate, False

    candidate = InvestmentCandidate(
        enterprise_id=card.enterprise_id,
        enterprise_name=card.enterprise_name,
        scenario_id=scenario.id,
        industry_chain_role=card.industry_chain_role,
        overall_score=card.overall_score,
        confidence=card.confidence,
        score_breakdown={
            key: value.model_dump(mode="json")
            for key, value in card.score_breakdown.items()
        },
        evidence=[item.model_dump(mode="json") for item in card.evidence],
        unknown_fields=card.unknown_fields,
        warnings=card.warnings,
        agent_outputs={
            key: value.model_dump(mode="json")
            for key, value in card.agent_outputs.items()
        },
        trace_refs=card.trace_refs,
        risk_level=card.risk.level,
        risk_summary=card.risk.reason,
        policy_matches=[
            item.model_dump(mode="json") for item in card.policy_matches
        ],
        recommendation=card.recommendation,
        next_action=card.next_action,
        status="NEW",
        source_task_id=scenario.source_task_id,
        data_mode=body.data_mode,
        created_by=user_id,
    )
    session.add(candidate)
    await session.flush()
    session.add(
        CandidateAudit(
            candidate_id=candidate.id,
            action="CREATED",
            actor_id=user_id,
            changes={
                "status": {"before": None, "after": "NEW"},
                "source": "scenario_recommendation_snapshot",
                "scenario_id": scenario.id,
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # The database unique constraint is the final idempotency boundary for
        # two users confirming the same recommendation concurrently.
        await session.rollback()
        raced = await session.execute(
            select(InvestmentCandidate).where(
                InvestmentCandidate.enterprise_id == card.enterprise_id,
                InvestmentCandidate.scenario_id == scenario.id,
                InvestmentCandidate.data_mode == body.data_mode,
            )
        )
        existing_candidate = raced.scalar_one_or_none()
        if existing_candidate is None:
            raise
        return existing_candidate, False
    await session.refresh(candidate)
    return candidate, True


async def list_candidates(
    session: AsyncSession,
    *,
    data_mode: str,
    status: str | None,
    assignee_id: str | None,
    limit: int,
    offset: int,
    cursor: str | None,
) -> CandidateListResponse:
    filters = [InvestmentCandidate.data_mode == data_mode]
    if status:
        filters.append(InvestmentCandidate.status == status)
    if assignee_id:
        filters.append(InvestmentCandidate.assignee_id == assignee_id)
    if cursor:
        cursor_item = await session.get(InvestmentCandidate, cursor)
        if cursor_item and cursor_item.data_mode == data_mode:
            filters.append(InvestmentCandidate.updated_at < cursor_item.updated_at)

    total_result = await session.execute(
        select(func.count(InvestmentCandidate.id)).where(*filters)
    )
    total = int(total_result.scalar_one())
    result = await session.execute(
        select(InvestmentCandidate)
        .where(*filters)
        .order_by(
            InvestmentCandidate.updated_at.desc(),
            InvestmentCandidate.id.desc(),
        )
        .offset(0 if cursor else offset)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return CandidateListResponse(
        items=[CandidateRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=0 if cursor else offset,
        next_cursor=items[-1].id if len(items) == limit else None,
        data_mode=data_mode,
    )


async def update_candidate(
    session: AsyncSession,
    candidate_id: str,
    body: CandidateUpdate,
    *,
    user_id: str,
) -> InvestmentCandidate:
    candidate = await session.get(InvestmentCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    changes = {}
    fields = body.model_fields_set
    if "status" in fields and body.status and body.status != candidate.status:
        allowed = ALLOWED_TRANSITIONS.get(candidate.status, set())
        if body.status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Invalid candidate transition: {candidate.status} -> {body.status}",
            )
        changes["status"] = {"before": candidate.status, "after": body.status}
        candidate.status = body.status

    for field in ("assignee_id", "next_action", "manual_note"):
        if field not in fields:
            continue
        before = getattr(candidate, field)
        after = getattr(body, field)
        if before != after:
            changes[field] = {"before": before, "after": after}
            setattr(candidate, field, after)

    if not changes:
        return candidate
    candidate.updated_at = _utcnow()
    session.add(
        CandidateAudit(
            candidate_id=candidate.id,
            action="UPDATED",
            actor_id=user_id,
            changes=changes,
        )
    )
    await session.commit()
    await session.refresh(candidate)
    return candidate


async def create_feedback(
    session: AsyncSession,
    candidate_id: str,
    body: CandidateFeedbackCreate,
    *,
    user_id: str,
) -> CandidateFeedback:
    candidate = await session.get(InvestmentCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    feedback = CandidateFeedback(
        candidate_id=candidate.id,
        decision=body.decision,
        reason_code=body.reason_code,
        comment=body.comment,
        reviewer_id=user_id,
    )
    session.add(feedback)
    status_before = candidate.status
    target_status = {
        "ACCEPT": "REVIEWED",
        "REJECT": "REJECTED",
        "NEED_MORE_EVIDENCE": "REVIEWED",
    }.get(body.decision)
    if (
        target_status
        and target_status != candidate.status
        and target_status in ALLOWED_TRANSITIONS.get(candidate.status, set())
    ):
        candidate.status = target_status
        candidate.updated_at = _utcnow()

    session.add(
        CandidateAudit(
            candidate_id=candidate.id,
            action="FEEDBACK_CREATED",
            actor_id=user_id,
            changes={
                "decision": body.decision,
                "reason_code": body.reason_code,
                "status": {
                    "before": status_before,
                    "after": candidate.status,
                },
            },
        )
    )
    await session.commit()
    await session.refresh(feedback)
    return feedback
