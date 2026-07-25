"""API v1 路由汇总 (P4: RBAC 权限保护)"""
from fastapi import APIRouter, Depends
from app.api.v1 import agent, task, trace, auth, dashboard, health, business, stream, admin
from app.core.security import require_user
from app.core.permissions import require_any_role

router = APIRouter()

router.include_router(auth.router, tags=["Auth"])
router.include_router(health.router, tags=["Health"])
router.include_router(agent.router, tags=["Agent"], dependencies=[Depends(require_user)])
router.include_router(task.router, tags=["Task"], dependencies=[Depends(require_user)])
router.include_router(trace.router, tags=["Trace"], dependencies=[Depends(require_user)])
router.include_router(stream.router, tags=["Stream"])  # P3: SSE 无需认证
router.include_router(dashboard.router, tags=["Dashboard"], dependencies=[Depends(require_user)])
router.include_router(business.router, tags=["Business"], dependencies=[Depends(require_user)])
# P4: Admin API (super_admin only)
router.include_router(admin.router, tags=["Admin"], dependencies=[Depends(require_any_role("super_admin"))])
