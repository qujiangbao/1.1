"""Persistence services for real investment follow-up and funnel facts."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.investment import (
    CandidateAudit,
    InvestmentCandidate,
    InvestmentCRMEvent,
    InvestmentFollowUpTask,
)
from app.schemas.investment_candidate import DataMode
from app.schemas.investment_crm import (
    CRMEventCreate,
    FollowUpTaskCreate,
    FollowUpTaskUpdate,
    FunnelStage,
    InvestmentFunnelRead,
    TaskStatus,
)


EVENT_STAGE = {
    "CONTACT": 1,
    "MEETING": 1,
    "NEGOTIATION": 2,
    "INTENT_SIGNED": 3,
    "CONTRACT_SIGNED": 3,
    "SETTLED": 4,
}


def _utc_naive(value: datetime | None) -> datetime | None:
    """Normalize API datetimes for the project's TIMESTAMP WITHOUT TIME ZONE columns."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _audit_value(value: object) -> object:
    """Keep audit JSON serializable while preserving an exact datetime value."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def _candidate_for_mode(
    session: AsyncSession,
    candidate_id: str,
    data_mode: DataMode,
) -> InvestmentCandidate:
    candidate = await session.get(InvestmentCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Investment candidate not found")
    if candidate.data_mode != data_mode:
        raise HTTPException(
            status_code=409,
            detail="CRM record and candidate data_mode must match",
        )
    return candidate


async def create_crm_event(
    session: AsyncSession,
    body: CRMEventCreate,
    *,
    user_id: str,
) -> InvestmentCRMEvent:
    candidate = await _candidate_for_mode(
        session,
        body.candidate_id,
        body.data_mode,
    )
    payload = body.model_dump()
    payload["occurred_at"] = _utc_naive(body.occurred_at)
    event = InvestmentCRMEvent(
        **payload,
        created_by=user_id,
    )
    session.add(event)
    session.add(
        CandidateAudit(
            candidate_id=candidate.id,
            action="CRM_EVENT_CREATED",
            actor_id=user_id,
            changes={
                "event_type": body.event_type,
                "occurred_at": body.occurred_at.isoformat(),
            },
        )
    )
    await session.commit()
    await session.refresh(event)
    return event


async def list_crm_events(
    session: AsyncSession,
    *,
    data_mode: DataMode,
    candidate_id: str | None,
    limit: int,
) -> list[InvestmentCRMEvent]:
    query = (
        select(InvestmentCRMEvent)
        .where(InvestmentCRMEvent.data_mode == data_mode)
        .order_by(
            InvestmentCRMEvent.occurred_at.desc(),
            InvestmentCRMEvent.created_at.desc(),
        )
        .limit(limit)
    )
    if candidate_id:
        query = query.where(InvestmentCRMEvent.candidate_id == candidate_id)
    return list((await session.execute(query)).scalars().all())


async def create_follow_up_task(
    session: AsyncSession,
    body: FollowUpTaskCreate,
    *,
    user_id: str,
) -> InvestmentFollowUpTask:
    candidate = await _candidate_for_mode(
        session,
        body.candidate_id,
        body.data_mode,
    )
    payload = body.model_dump()
    payload["due_at"] = _utc_naive(body.due_at)
    task = InvestmentFollowUpTask(
        **payload,
        status="TODO",
        created_by=user_id,
    )
    session.add(task)
    session.add(
        CandidateAudit(
            candidate_id=candidate.id,
            action="FOLLOW_UP_TASK_CREATED",
            actor_id=user_id,
            changes={
                "title": body.title,
                "owner_id": body.owner_id,
                "due_at": body.due_at.isoformat() if body.due_at else None,
            },
        )
    )
    await session.commit()
    await session.refresh(task)
    return task


async def list_follow_up_tasks(
    session: AsyncSession,
    *,
    data_mode: DataMode,
    status: TaskStatus | None,
    owner_id: str | None,
    candidate_id: str | None,
    limit: int,
) -> list[InvestmentFollowUpTask]:
    filters = [InvestmentFollowUpTask.data_mode == data_mode]
    if status:
        filters.append(InvestmentFollowUpTask.status == status)
    if owner_id:
        filters.append(InvestmentFollowUpTask.owner_id == owner_id)
    if candidate_id:
        filters.append(InvestmentFollowUpTask.candidate_id == candidate_id)
    query = (
        select(InvestmentFollowUpTask)
        .where(*filters)
        .order_by(
            InvestmentFollowUpTask.due_at.asc().nullslast(),
            InvestmentFollowUpTask.updated_at.desc(),
        )
        .limit(limit)
    )
    return list((await session.execute(query)).scalars().all())


async def update_follow_up_task(
    session: AsyncSession,
    task_id: str,
    body: FollowUpTaskUpdate,
    *,
    user_id: str,
) -> InvestmentFollowUpTask:
    task = await session.get(InvestmentFollowUpTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Follow-up task not found")
    changes: dict[str, dict[str, object]] = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "due_at":
            value = _utc_naive(value)
        before = getattr(task, field)
        if before != value:
            changes[field] = {
                "before": _audit_value(before),
                "after": _audit_value(value),
            }
            setattr(task, field, value)
    if not changes:
        return task
    task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(
        CandidateAudit(
            candidate_id=task.candidate_id,
            action="FOLLOW_UP_TASK_UPDATED",
            actor_id=user_id,
            changes=changes,
        )
    )
    await session.commit()
    await session.refresh(task)
    return task


async def get_investment_funnel(
    session: AsyncSession,
    *,
    data_mode: DataMode,
) -> InvestmentFunnelRead:
    target_count = int(
        (
            await session.execute(
                select(func.count(InvestmentCandidate.id)).where(
                    InvestmentCandidate.data_mode == data_mode,
                    InvestmentCandidate.status.notin_(["REJECTED", "ARCHIVED"]),
                )
            )
        ).scalar()
        or 0
    )
    event_stage = case(
        *[
            (InvestmentCRMEvent.event_type == event_type, stage)
            for event_type, stage in EVENT_STAGE.items()
        ],
        else_=0,
    )
    latest_stages = (
        select(
            InvestmentCRMEvent.candidate_id.label("candidate_id"),
            func.max(event_stage).label("max_stage"),
        )
        .where(InvestmentCRMEvent.data_mode == data_mode)
        .group_by(InvestmentCRMEvent.candidate_id)
        .subquery()
    )
    stage_counts = {
        int(stage): int(count)
        for stage, count in (
            await session.execute(
                select(latest_stages.c.max_stage, func.count())
                .group_by(latest_stages.c.max_stage)
            )
        ).all()
    }
    cumulative = {
        stage: sum(count for value, count in stage_counts.items() if value >= stage)
        for stage in range(1, 5)
    }
    return InvestmentFunnelRead(
        data_mode=data_mode,
        source="investment_crm_event",
        generated_at=datetime.now(timezone.utc),
        stages=[
            FunnelStage(stage="TARGET", label="目标池", count=target_count),
            FunnelStage(stage="CONTACT", label="已接触", count=cumulative[1]),
            FunnelStage(stage="NEGOTIATION", label="洽谈中", count=cumulative[2]),
            FunnelStage(stage="SIGNED", label="已签约", count=cumulative[3]),
            FunnelStage(stage="SETTLED", label="已入驻", count=cumulative[4]),
        ],
    )
