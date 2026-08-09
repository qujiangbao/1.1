"""Auth API — P4: Login / Refresh / Me (DB-backed)"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.security import (
    create_access_token, create_refresh_token, verify_token,
    verify_password, UserContext, require_user,
)
from app.schemas.agent import LoginRequest
from app.config import get_settings

router = APIRouter()
settings = get_settings()
_DUMMY_PASSWORD_HASH = (
    "$2b$12$daYugG3QcE8trOOH71GRPuzGIZQgENjPLoXqIn5lK4wMtOj4SZYL2"
)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/auth/login")
async def login(request: LoginRequest):
    """用户登录 → 返回 Access Token + Refresh Token

    AUTH_ENABLED=false → 使用硬编码 admin/admin
    AUTH_ENABLED=true  → 查询 users 表 + 密码验证
    """
    if not settings.auth_enabled:
        # v1.2 兼容: 硬编码 admin/admin
        from hmac import compare_digest
        if not (compare_digest(request.username, settings.admin_username) and
                compare_digest(request.password, settings.admin_password)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = create_access_token({
            "sub": "demo-user", "username": "admin", "role": "park_manager",
        })
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {"id": "demo-user", "username": "admin", "role": "park_manager", "display_name": "管理员"},
        }

    # P4: DB-backed 登录
    if not settings.database_enabled:
        raise HTTPException(status_code=503, detail="Database not available for auth")

    from app.database.session import SessionLocal
    from app.database.models.rbac import User, UserRole, Role
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == request.username)
        )
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            # Keep missing/disabled-account timing close to a real bcrypt check.
            verify_password(request.password, _DUMMY_PASSWORD_HASH)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get role
        role_result = await db.execute(
            select(Role.name).join(UserRole).where(UserRole.user_id == user.user_id)
        )
        role_name = role_result.scalar_one_or_none() or "viewer"

        access_token = create_access_token({
            "sub": user.user_id,
            "username": user.username,
            "role": role_name,
            "park_id": user.park_id,
        })
        refresh_token = create_refresh_token(user.user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.user_id,
                "username": user.username,
                "role": role_name,
                "display_name": user.display_name,
            },
        }


@router.post("/auth/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access credentials without exposing tokens in URL logs."""
    payload = verify_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]

    # 查找用户
    if settings.database_enabled:
        from app.database.session import SessionLocal
        from app.database.models.rbac import User, UserRole, Role
        from sqlalchemy import select
        async with SessionLocal() as db:
            result = await db.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if user is None or not user.is_active:
                raise HTTPException(status_code=403, detail="User inactive or not found")
            role_result = await db.execute(
                select(Role.name).join(UserRole).where(UserRole.user_id == user_id)
            )
            role_name = role_result.scalar_one_or_none() or "viewer"
            new_token = create_access_token({
                "sub": user_id, "username": user.username,
                "role": role_name, "park_id": user.park_id,
            })
    else:
        new_token = create_access_token({
            "sub": user_id, "username": user_id, "role": "park_manager",
        })

    return {
        "access_token": new_token,
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


@router.get("/auth/me")
async def get_current_user(user: UserContext = Depends(require_user)):
    """返回当前登录用户信息"""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "park_id": user.park_id,
    }
