"""API v1 路由汇总"""
from fastapi import APIRouter, Depends
from app.api.v1 import agent, task, trace, auth, dashboard, health, business, stream
from app.core.security import require_user

router = APIRouter()

router.include_router(auth.router, tags=["Auth"])
router.include_router(health.router, tags=["Health"])
router.include_router(agent.router, tags=["Agent"], dependencies=[Depends(require_user)])
router.include_router(task.router, tags=["Task"], dependencies=[Depends(require_user)])
router.include_router(trace.router, tags=["Trace"], dependencies=[Depends(require_user)])
router.include_router(stream.router, tags=["Stream"])  # P3: 无需认证 (SSE EventSource 不支持 header)
router.include_router(dashboard.router, tags=["Dashboard"], dependencies=[Depends(require_user)])
router.include_router(business.router, tags=["Business"], dependencies=[Depends(require_user)])
