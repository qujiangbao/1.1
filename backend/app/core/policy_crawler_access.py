"""Fail-closed authorization for the privileged policy crawler."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.core.security import UserContext, require_user


ROOT_ADMIN_USER_ID = "user-admin-001"


def is_root_admin(user: UserContext) -> bool:
    return user.user_id == ROOT_ADMIN_USER_ID and user.role == "super_admin"


async def crawler_access_state(user: UserContext) -> dict:
    settings = get_settings()
    if not settings.auth_enabled or not settings.database_enabled:
        return {
            "allowed": False,
            "is_root_admin": False,
            "status": "UNAVAILABLE",
            "reason": "政策更新中心要求启用数据库认证，演示免认证模式下禁止执行爬虫。",
        }
    if user.role != "super_admin":
        return {
            "allowed": False,
            "is_root_admin": False,
            "status": "FORBIDDEN",
            "reason": "仅超级管理员可以申请政策爬虫权限。",
        }
    if is_root_admin(user):
        return {
            "allowed": True,
            "is_root_admin": True,
            "status": "OWNER",
            "reason": "初始admin拥有政策更新审批权和执行权。",
        }

    try:
        from app.database.models.policy_crawler import PolicyCrawlerGrant
        from app.database.session import SessionLocal

        if SessionLocal is None:
            raise RuntimeError("database session unavailable")
        async with SessionLocal() as session:
            grant = (
                await session.execute(
                    select(PolicyCrawlerGrant).where(
                        PolicyCrawlerGrant.user_id == user.user_id
                    )
                )
            ).scalar_one_or_none()
        if grant is not None and grant.status == "APPROVED":
            return {
                "allowed": True,
                "is_root_admin": False,
                "status": "APPROVED",
                "reason": "已由初始admin批准。",
            }
        return {
            "allowed": False,
            "is_root_admin": False,
            "status": "REVOKED" if grant is not None else "NOT_REQUESTED",
            "reason": "需要初始admin批准后才能运行政策爬虫。",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "无法核验政策爬虫授权，已拒绝执行") from exc


async def require_policy_crawler_access(
    user: UserContext = Depends(require_user),
) -> UserContext:
    state = await crawler_access_state(user)
    if not state["allowed"]:
        raise HTTPException(403, state["reason"])
    return user


async def require_policy_crawler_owner(
    user: UserContext = Depends(require_user),
) -> UserContext:
    settings = get_settings()
    if not settings.auth_enabled or not settings.database_enabled:
        raise HTTPException(503, "数据库认证未启用，政策爬虫审批功能不可用")
    if not is_root_admin(user):
        raise HTTPException(403, "只有初始admin可以审批政策爬虫权限")
    return user
