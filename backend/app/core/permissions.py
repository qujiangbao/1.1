"""RBAC Permissions Middleware — P4 基于角色的访问控制

require_role()       — 要求用户拥有指定角色
require_permission() — 要求用户拥有指定权限
require_agent_access() — 要求用户可调用指定 Agent"""

from fastapi import Depends, HTTPException
from app.core.security import UserContext, require_user

# 角色层级 (数字越大权限越高)
ROLE_HIERARCHY = {
    "viewer": 0,
    "enterprise_service": 1,
    "policy_manager": 2,
    "investment_manager": 3,
    "park_manager": 4,
    "super_admin": 5,
}


def require_min_role(min_role: str):
    """要求用户角色 >= min_role"""
    async def checker(user: UserContext = Depends(require_user)):
        user_level = ROLE_HIERARCHY.get(user.role, -1)
        required_level = ROLE_HIERARCHY.get(min_role, 999)
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role '{min_role}' or higher (current: {user.role})",
            )
        return user
    return checker


def require_any_role(*roles: str):
    """要求用户拥有任一角色"""
    async def checker(user: UserContext = Depends(require_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {', '.join(roles)} (current: {user.role})",
            )
        return user
    return checker


def require_permission(perm_code: str):
    """要求用户拥有指定权限 code"""
    async def checker(user: UserContext = Depends(require_user)):
        from app.config import get_settings
        if not get_settings().database_enabled:
            return user  # DB disabled → 允许所有

        try:
            from app.database.session import SessionLocal
            from app.database.models.rbac import UserRole, RolePermission, Permission
            from sqlalchemy import select

            async with SessionLocal() as db:
                # Check if user has any role with this permission
                result = await db.execute(
                    select(Permission).join(RolePermission).join(UserRole)
                    .where(UserRole.user_id == user.user_id)
                    .where(Permission.code == perm_code)
                )
                if result.scalar_one_or_none() is None:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Missing permission: {perm_code}",
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # DB error → allow (fail open in dev)
        return user
    return checker


def require_agent_access(agent_name: str):
    """要求用户可调用指定 Agent"""
    return require_permission(f"agent:{_agent_to_code(agent_name)}")


# ═══ Agent Name → Permission Code ═══

AGENT_CODE_MAP = {
    "InvestmentAgent":         "investment",
    "PolicyAgent":             "policy",
    "IndustryAgent":           "industry",
    "RiskAgent":               "risk",
    "EnterpriseServiceAgent":  "service",
    "BIAgent":                 "bi",
}


def _agent_to_code(agent_name: str) -> str:
    return AGENT_CODE_MAP.get(agent_name, agent_name.lower())


# ═══ Task Planner: Role → Allowed Agents ═══

ROLE_AGENT_WHITELIST = {
    "super_admin":          ["*"],
    "park_manager":         ["*"],
    "investment_manager":   ["InvestmentAgent", "IndustryAgent", "RiskAgent", "BIAgent"],
    "policy_manager":       ["PolicyAgent", "BIAgent"],
    "enterprise_service":   ["EnterpriseServiceAgent", "BIAgent"],
    "viewer":               ["BIAgent"],
}


def user_can_use_agent(user_role: str, agent_name: str) -> bool:
    """检查用户角色是否可以调用指定 Agent"""
    allowed = ROLE_AGENT_WHITELIST.get(user_role, [])
    if "*" in allowed:
        return True
    return agent_name in allowed
