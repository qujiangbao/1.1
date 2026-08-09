"""Exposure-aware, offline-only ranking analysis.

This module never writes scoring weights.  It produces a reviewable proposal
only after minimum sample and cohort thresholds are met.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.investment import (
    CandidateFeedback,
    InvestmentCandidate,
    InvestmentScenario,
    RecommendationExposure,
)
from app.schemas.investment_candidate import DataMode
from app.schemas.investment_crm import RecommendationExposureCreate


BASELINE_WEIGHTS = {
    "industry_fit": 0.30,
    "technology": 0.20,
    "growth": 0.15,
    "landing_intent": 0.10,
    "policy_fit": 0.15,
    "data_completeness": 0.10,
}
MIN_FEEDBACK = 100
MIN_COHORT = 30


async def record_recommendation_exposures(
    session: AsyncSession,
    scenario_id: str,
    body: RecommendationExposureCreate,
    *,
    user_id: str,
) -> int:
    scenario = await session.get(InvestmentScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Investment scenario not found")
    if scenario.data_mode != body.data_mode:
        raise HTTPException(
            status_code=409,
            detail="Exposure and scenario data_mode must match",
        )
    enterprise_ids = {item.enterprise_id for item in body.items}
    existing = set(
        (
            await session.execute(
                select(RecommendationExposure.enterprise_id).where(
                    RecommendationExposure.scenario_id == scenario_id,
                    RecommendationExposure.user_id == user_id,
                    RecommendationExposure.event_type == body.event_type,
                    RecommendationExposure.enterprise_id.in_(enterprise_ids),
                )
            )
        ).scalars().all()
    )
    created = 0
    for item in body.items:
        if item.enterprise_id in existing:
            continue
        session.add(
            RecommendationExposure(
                scenario_id=scenario_id,
                enterprise_id=item.enterprise_id,
                user_id=user_id,
                event_type=body.event_type,
                position=item.position,
                score=item.score,
                data_mode=body.data_mode,
                context=body.context,
            )
        )
        created += 1
    if created:
        await session.commit()
    return created


def _dimension_score(candidate: InvestmentCandidate, key: str) -> float | None:
    item = (candidate.score_breakdown or {}).get(key) or {}
    value = item.get("score")
    return float(value) if isinstance(value, (int, float)) else None


async def build_offline_learning_report(
    session: AsyncSession,
    *,
    data_mode: DataMode,
) -> dict:
    impression_count = int(
        (
            await session.execute(
                select(func.count(RecommendationExposure.id)).where(
                    RecommendationExposure.data_mode == data_mode,
                    RecommendationExposure.event_type == "IMPRESSION",
                )
            )
        ).scalar()
        or 0
    )
    rows = (
        await session.execute(
            select(CandidateFeedback, InvestmentCandidate)
            .join(
                InvestmentCandidate,
                InvestmentCandidate.id == CandidateFeedback.candidate_id,
            )
            .where(
                InvestmentCandidate.data_mode == data_mode,
                CandidateFeedback.decision.in_(["ACCEPT", "REJECT"]),
            )
        )
    ).all()
    accepted = [
        candidate
        for feedback, candidate in rows
        if feedback.decision == "ACCEPT"
    ]
    rejected = [
        candidate
        for feedback, candidate in rows
        if feedback.decision == "REJECT"
    ]
    ready = (
        impression_count >= MIN_FEEDBACK
        and len(rows) >= MIN_FEEDBACK
        and len(accepted) >= MIN_COHORT
        and len(rejected) >= MIN_COHORT
    )
    proposed_weights = None
    dimension_diagnostics = {}
    if ready:
        raw = {}
        for key, baseline in BASELINE_WEIGHTS.items():
            accepted_scores = [
                score
                for candidate in accepted
                if (score := _dimension_score(candidate, key)) is not None
            ]
            rejected_scores = [
                score
                for candidate in rejected
                if (score := _dimension_score(candidate, key)) is not None
            ]
            accepted_mean = (
                sum(accepted_scores) / len(accepted_scores)
                if accepted_scores
                else None
            )
            rejected_mean = (
                sum(rejected_scores) / len(rejected_scores)
                if rejected_scores
                else None
            )
            gap = (
                accepted_mean - rejected_mean
                if accepted_mean is not None and rejected_mean is not None
                else 0
            )
            delta = max(-0.03, min(gap / 1000, 0.03))
            raw[key] = max(0.05, baseline + delta)
            dimension_diagnostics[key] = {
                "accepted_count": len(accepted_scores),
                "rejected_count": len(rejected_scores),
                "accepted_mean": accepted_mean,
                "rejected_mean": rejected_mean,
                "bounded_delta": round(delta, 4),
            }
        total = sum(raw.values())
        proposed_weights = {
            key: round(value / total, 4)
            for key, value in raw.items()
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": data_mode,
        "mode": "OFFLINE_PROPOSAL_ONLY",
        "ready": ready,
        "activation_allowed": False,
        "thresholds": {
            "minimum_impressions": MIN_FEEDBACK,
            "minimum_labeled_feedback": MIN_FEEDBACK,
            "minimum_accept_cohort": MIN_COHORT,
            "minimum_reject_cohort": MIN_COHORT,
        },
        "sample": {
            "impressions": impression_count,
            "labeled_feedback": len(rows),
            "accepted": len(accepted),
            "rejected": len(rejected),
        },
        "baseline_weights": BASELINE_WEIGHTS,
        "proposed_weights": proposed_weights,
        "dimension_diagnostics": dimension_diagnostics,
        "reason": (
            "样本门槛满足，可进入人工评审与离线回放；仍不会自动上线。"
            if ready
            else "曝光或正负反馈样本不足，保持当前确定性排序。"
        ),
    }
