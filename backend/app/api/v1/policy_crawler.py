"""Governed policy-crawler API.

Crawler execution is intentionally separated from ordinary ``super_admin``
RBAC.  The bootstrap admin owns approval; later super administrators need an
explicit grant and all checks fail closed.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.permissions import require_any_role
from app.core.policy_crawler_access import (
    ROOT_ADMIN_USER_ID,
    crawler_access_state,
    require_policy_crawler_access,
    require_policy_crawler_owner,
)
from app.core.security import UserContext


router = APIRouter(prefix="/policy-crawler")


class AccessRequestCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class AccessDecision(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    note: str | None = Field(default=None, max_length=1000)


class CrawlRunCreate(BaseModel):
    pages: int = Field(default=3, ge=1, le=20)
    workers: int = Field(default=3, ge=1, le=3)
    force: bool = False


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _run_payload(run) -> dict:
    return {
        "run_id": run.run_id,
        "requested_by": run.requested_by,
        "status": run.status,
        "pages": run.pages,
        "workers": run.workers,
        "force": run.force,
        "stats": run.stats or {},
        "error": run.error,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


@router.get("/access")
async def get_access(
    user: UserContext = Depends(require_any_role("super_admin")),
):
    state = await crawler_access_state(user)
    if state["status"] in {"NOT_REQUESTED", "REVOKED"}:
        from app.database.models.policy_crawler import PolicyCrawlerAccessRequest
        from app.database.session import SessionLocal

        if SessionLocal is not None:
            async with SessionLocal() as session:
                pending = (
                    await session.execute(
                        select(PolicyCrawlerAccessRequest)
                        .where(
                            PolicyCrawlerAccessRequest.requester_id == user.user_id,
                            PolicyCrawlerAccessRequest.status == "PENDING",
                        )
                        .order_by(PolicyCrawlerAccessRequest.requested_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if pending is not None:
                    state = {
                        **state,
                        "status": "PENDING",
                        "reason": "权限申请等待初始admin审批。",
                        "request_id": pending.request_id,
                    }
    return {"success": True, "data": state}


@router.post("/access/requests", status_code=201)
async def request_access(
    body: AccessRequestCreate,
    user: UserContext = Depends(require_any_role("super_admin")),
):
    if user.user_id == ROOT_ADMIN_USER_ID:
        raise HTTPException(409, "初始admin已拥有政策爬虫权限")
    from app.database.models.policy_crawler import (
        PolicyCrawlerAccessRequest,
        PolicyCrawlerGrant,
    )
    from app.database.session import SessionLocal

    if SessionLocal is None:
        raise HTTPException(503, "数据库不可用")
    async with SessionLocal() as session:
        grant = await session.get(PolicyCrawlerGrant, user.user_id)
        if grant is not None and grant.status == "APPROVED":
            raise HTTPException(409, "当前账号已获得政策爬虫权限")
        pending = (
            await session.execute(
                select(PolicyCrawlerAccessRequest).where(
                    PolicyCrawlerAccessRequest.requester_id == user.user_id,
                    PolicyCrawlerAccessRequest.status == "PENDING",
                )
            )
        ).scalar_one_or_none()
        if pending is not None:
            raise HTTPException(409, "已有等待审批的申请")
        request = PolicyCrawlerAccessRequest(
            request_id=str(uuid4()),
            requester_id=user.user_id,
            reason=body.reason,
            status="PENDING",
        )
        session.add(request)
        await session.commit()
        return {"success": True, "data": {"request_id": request.request_id, "status": request.status}}


@router.get("/access/requests")
async def list_access_requests(
    status: str | None = Query(default=None, pattern="^(PENDING|APPROVED|REJECTED|CANCELLED)$"),
    _owner: UserContext = Depends(require_policy_crawler_owner),
):
    from app.database.models.policy_crawler import PolicyCrawlerAccessRequest
    from app.database.models.rbac import User
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        statement = (
            select(PolicyCrawlerAccessRequest, User)
            .join(User, User.user_id == PolicyCrawlerAccessRequest.requester_id)
            .order_by(PolicyCrawlerAccessRequest.requested_at.desc())
        )
        if status:
            statement = statement.where(PolicyCrawlerAccessRequest.status == status)
        rows = (await session.execute(statement)).all()
        return {
            "success": True,
            "data": [
                {
                    "request_id": request.request_id,
                    "requester_id": request.requester_id,
                    "username": account.username,
                    "display_name": account.display_name,
                    "reason": request.reason,
                    "status": request.status,
                    "decided_by": request.decided_by,
                    "decision_note": request.decision_note,
                    "requested_at": _iso(request.requested_at),
                    "decided_at": _iso(request.decided_at),
                }
                for request, account in rows
            ],
        }


@router.patch("/access/requests/{request_id}")
async def decide_access_request(
    request_id: str,
    body: AccessDecision,
    owner: UserContext = Depends(require_policy_crawler_owner),
):
    from app.database.models.policy_crawler import (
        PolicyCrawlerAccessRequest,
        PolicyCrawlerGrant,
    )
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        request = await session.get(PolicyCrawlerAccessRequest, request_id)
        if request is None:
            raise HTTPException(404, "权限申请不存在")
        if request.status != "PENDING":
            raise HTTPException(409, "该申请已经处理")
        request.status = body.decision
        request.decided_by = owner.user_id
        request.decision_note = body.note
        request.decided_at = datetime.utcnow()
        if body.decision == "APPROVED":
            grant = await session.get(PolicyCrawlerGrant, request.requester_id)
            if grant is None:
                grant = PolicyCrawlerGrant(
                    user_id=request.requester_id,
                    approved_by=owner.user_id,
                )
                session.add(grant)
            grant.status = "APPROVED"
            grant.approved_by = owner.user_id
            grant.approved_at = datetime.utcnow()
            grant.revoked_by = None
            grant.revoked_at = None
        await session.commit()
        return {"success": True, "data": {"request_id": request_id, "status": request.status}}


@router.get("/access/grants")
async def list_grants(
    _owner: UserContext = Depends(require_policy_crawler_owner),
):
    from app.database.models.policy_crawler import PolicyCrawlerGrant
    from app.database.models.rbac import User
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(PolicyCrawlerGrant, User)
                .join(User, User.user_id == PolicyCrawlerGrant.user_id)
                .order_by(PolicyCrawlerGrant.approved_at.desc())
            )
        ).all()
        return {
            "success": True,
            "data": [
                {
                    "user_id": grant.user_id,
                    "username": account.username,
                    "display_name": account.display_name,
                    "status": grant.status,
                    "approved_by": grant.approved_by,
                    "approved_at": _iso(grant.approved_at),
                    "revoked_by": grant.revoked_by,
                    "revoked_at": _iso(grant.revoked_at),
                }
                for grant, account in rows
            ],
        }


@router.delete("/access/grants/{user_id}")
async def revoke_grant(
    user_id: str,
    owner: UserContext = Depends(require_policy_crawler_owner),
):
    if user_id == ROOT_ADMIN_USER_ID:
        raise HTTPException(409, "不能撤销初始admin的所有者权限")
    from app.database.models.policy_crawler import PolicyCrawlerGrant
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        grant = await session.get(PolicyCrawlerGrant, user_id)
        if grant is None or grant.status != "APPROVED":
            raise HTTPException(404, "有效授权不存在")
        grant.status = "REVOKED"
        grant.revoked_by = owner.user_id
        grant.revoked_at = datetime.utcnow()
        await session.commit()
        return {"success": True, "data": {"user_id": user_id, "status": "REVOKED"}}


@router.post("/runs", status_code=202)
async def create_run(
    body: CrawlRunCreate,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_policy_crawler_access),
):
    if body.force and user.user_id != ROOT_ADMIN_USER_ID:
        raise HTTPException(403, "只有初始admin可以执行强制全量刷新")
    from app.database.models.policy_crawler import PolicyCrawlRun
    from app.database.session import SessionLocal
    from app.services.policy_crawler_service import execute_policy_crawl_run

    async with SessionLocal() as session:
        run = PolicyCrawlRun(
            run_id=str(uuid4()),
            requested_by=user.user_id,
            status="QUEUED",
            pages=body.pages,
            workers=body.workers,
            force=body.force,
        )
        session.add(run)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(409, "已有政策更新任务正在运行") from exc
        await session.refresh(run)
        payload = _run_payload(run)
    background_tasks.add_task(execute_policy_crawl_run, run.run_id)
    return {"success": True, "data": payload}


@router.get("/runs")
async def list_runs(
    limit: int = Query(default=30, ge=1, le=100),
    _user: UserContext = Depends(require_policy_crawler_access),
):
    from app.database.models.policy_crawler import PolicyCrawlRun
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        runs = list(
            (
                await session.execute(
                    select(PolicyCrawlRun)
                    .order_by(PolicyCrawlRun.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
        )
        return {"success": True, "data": [_run_payload(run) for run in runs]}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    _user: UserContext = Depends(require_policy_crawler_access),
):
    from app.database.models.policy_crawler import PolicyCrawlRun
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        run = await session.get(PolicyCrawlRun, run_id)
        if run is None:
            raise HTTPException(404, "政策更新任务不存在")
        return {"success": True, "data": _run_payload(run)}
