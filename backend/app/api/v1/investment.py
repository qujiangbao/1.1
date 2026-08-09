"""Investment decision-loop API: scenarios, candidates and human feedback."""
from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import app.database.session as database_session
from app.core.permissions import require_any_role
from app.core.data_mode import require_allowed_data_mode
from app.core.security import UserContext, create_stream_token, require_user
from app.database.models.investment import InvestmentScenario
from app.schemas.investment_candidate import (
    CandidateCreate,
    CandidateFeedbackCreate,
    CandidateFeedbackRead,
    CandidateRead,
    CandidateStatus,
    CandidateUpdate,
    DataMode,
    InvestmentScenarioCreate,
    InvestmentScenarioCreated,
)
from app.schemas.investment_crm import (
    CRMEventCreate,
    CRMEventRead,
    FollowUpTaskCreate,
    FollowUpTaskRead,
    FollowUpTaskUpdate,
    RecommendationExposureCreate,
    TaskStatus,
)
from app.services.investment_candidate_service import (
    create_candidate,
    create_feedback,
    list_candidates,
    update_candidate,
)
from app.services.investment_evaluation_service import (
    create_scenario,
    scenario_response,
)
from app.services.investment_pdf_service import render_investment_scenario_pdf
from app.services.investment_learning_service import (
    build_offline_learning_report,
    record_recommendation_exposures,
)
from app.services.investment_crm_service import (
    create_crm_event,
    create_follow_up_task,
    get_investment_funnel,
    list_crm_events,
    list_follow_up_tasks,
    update_follow_up_task,
)


router = APIRouter()
WRITE_ROLES = ("super_admin", "park_manager", "investment_manager")
EVALUATION_REPORT = (
    Path(__file__).resolve().parents[3]
    / "reports"
    / "investment_public_30_latest.json"
)


async def investment_db() -> AsyncIterator[AsyncSession]:
    if database_session.SessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="Candidate persistence requires DATABASE_ENABLED=true",
        )
    async with database_session.SessionLocal() as session:
        yield session


@router.post(
    "/investment/scenarios",
    response_model=InvestmentScenarioCreated,
    status_code=201,
)
async def create_investment_scenario(
    body: InvestmentScenarioCreate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    require_allowed_data_mode(body.data_mode)
    scenario = await create_scenario(session, body, user_id=user.user_id)
    stream_token = (
        create_stream_token(scenario.source_task_id, user.user_id)
        if scenario.source_task_id
        else None
    )
    return InvestmentScenarioCreated(
        scenario_id=scenario.id,
        task_id=scenario.source_task_id,
        stream_url=(
            f"/api/v1/agent/stream/{scenario.source_task_id}?token={stream_token}"
            if scenario.source_task_id and stream_token
            else None
        ),
        status=scenario.status,
    )


@router.get("/investment/scenarios/{scenario_id}/recommendations")
async def get_scenario_recommendations(
    scenario_id: str,
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    scenario = await session.get(InvestmentScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Investment scenario not found")
    return {"success": True, "data": scenario_response(scenario).model_dump(mode="json")}


@router.get("/investment/scenarios/{scenario_id}/report.pdf")
async def export_scenario_pdf(
    scenario_id: str,
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    scenario = await session.get(InvestmentScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Investment scenario not found")
    pdf = render_investment_scenario_pdf(scenario)
    safe_id = "".join(
        character for character in scenario.id
        if character.isalnum() or character in {"-", "_"}
    )
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="investment-report-{safe_id}.pdf"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/investment/evaluation/latest")
async def get_latest_investment_evaluation(
    _user: UserContext = Depends(require_user),
):
    if not EVALUATION_REPORT.exists():
        raise HTTPException(
            status_code=404,
            detail="Investment evaluation report has not been generated",
        )
    return {
        "success": True,
        "data": json.loads(EVALUATION_REPORT.read_text(encoding="utf-8")),
    }


@router.post("/investment/scenarios/{scenario_id}/exposures")
async def post_recommendation_exposures(
    scenario_id: str,
    body: RecommendationExposureCreate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_user),
):
    require_allowed_data_mode(body.data_mode)
    created = await record_recommendation_exposures(
        session,
        scenario_id,
        body,
        user_id=user.user_id,
    )
    return {"success": True, "created": created}


@router.get("/investment/learning/offline-report")
async def get_offline_learning_report(
    data_mode: DataMode = "real",
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(
        require_any_role("super_admin", "park_manager", "investment_manager")
    ),
):
    data_mode = require_allowed_data_mode(data_mode)
    report = await build_offline_learning_report(
        session,
        data_mode=data_mode,
    )
    return {"success": True, "data": report}


@router.post("/investment/candidates")
async def add_investment_candidate(
    body: CandidateCreate,
    response: Response,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    require_allowed_data_mode(body.data_mode)
    candidate, created = await create_candidate(
        session,
        body,
        user_id=user.user_id,
    )
    response.status_code = 201 if created else 200
    return {
        "success": True,
        "created": created,
        "data": CandidateRead.model_validate(candidate).model_dump(mode="json"),
    }


@router.get("/investment/candidates")
async def get_investment_candidates(
    status: CandidateStatus | None = None,
    assignee_id: str | None = None,
    data_mode: DataMode = "real",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = None,
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    data_mode = require_allowed_data_mode(data_mode)
    result = await list_candidates(
        session,
        data_mode=data_mode,
        status=status,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
        cursor=cursor,
    )
    return {"success": True, "data": result.model_dump(mode="json")}


@router.patch("/investment/candidates/{candidate_id}")
async def patch_investment_candidate(
    candidate_id: str,
    body: CandidateUpdate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    candidate = await update_candidate(
        session,
        candidate_id,
        body,
        user_id=user.user_id,
    )
    return {
        "success": True,
        "data": CandidateRead.model_validate(candidate).model_dump(mode="json"),
    }


@router.post(
    "/investment/candidates/{candidate_id}/feedback",
    status_code=201,
)
async def submit_candidate_feedback(
    candidate_id: str,
    body: CandidateFeedbackCreate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    feedback = await create_feedback(
        session,
        candidate_id,
        body,
        user_id=user.user_id,
    )
    return {
        "success": True,
        "data": CandidateFeedbackRead.model_validate(feedback).model_dump(mode="json"),
    }


@router.post("/investment/crm/events", status_code=201)
async def post_investment_crm_event(
    body: CRMEventCreate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    require_allowed_data_mode(body.data_mode)
    event = await create_crm_event(session, body, user_id=user.user_id)
    return {
        "success": True,
        "data": CRMEventRead.model_validate(event).model_dump(mode="json"),
    }


@router.get("/investment/crm/events")
async def get_investment_crm_events(
    candidate_id: str | None = None,
    data_mode: DataMode = "real",
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    data_mode = require_allowed_data_mode(data_mode)
    events = await list_crm_events(
        session,
        data_mode=data_mode,
        candidate_id=candidate_id,
        limit=limit,
    )
    return {
        "success": True,
        "data": [
            CRMEventRead.model_validate(item).model_dump(mode="json")
            for item in events
        ],
    }


@router.get("/investment/crm/funnel")
async def get_real_investment_funnel(
    data_mode: DataMode = "real",
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    data_mode = require_allowed_data_mode(data_mode)
    funnel = await get_investment_funnel(session, data_mode=data_mode)
    return {"success": True, "data": funnel.model_dump(mode="json")}


@router.post("/investment/follow-up-tasks", status_code=201)
async def post_investment_follow_up_task(
    body: FollowUpTaskCreate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    require_allowed_data_mode(body.data_mode)
    task = await create_follow_up_task(session, body, user_id=user.user_id)
    return {
        "success": True,
        "data": FollowUpTaskRead.model_validate(task).model_dump(mode="json"),
    }


@router.get("/investment/follow-up-tasks")
async def get_investment_follow_up_tasks(
    candidate_id: str | None = None,
    owner_id: str | None = None,
    status: TaskStatus | None = None,
    data_mode: DataMode = "real",
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_user),
):
    data_mode = require_allowed_data_mode(data_mode)
    tasks = await list_follow_up_tasks(
        session,
        data_mode=data_mode,
        status=status,
        owner_id=owner_id,
        candidate_id=candidate_id,
        limit=limit,
    )
    return {
        "success": True,
        "data": [
            FollowUpTaskRead.model_validate(item).model_dump(mode="json")
            for item in tasks
        ],
    }


@router.patch("/investment/follow-up-tasks/{task_id}")
async def patch_investment_follow_up_task(
    task_id: str,
    body: FollowUpTaskUpdate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    task = await update_follow_up_task(
        session,
        task_id,
        body,
        user_id=user.user_id,
    )
    return {
        "success": True,
        "data": FollowUpTaskRead.model_validate(task).model_dump(mode="json"),
    }
