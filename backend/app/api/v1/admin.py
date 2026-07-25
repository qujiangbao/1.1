"""Admin API — P4 User Management (super_admin only)"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.permissions import require_any_role
from app.core.security import UserContext

router = APIRouter()


@router.get("/admin/users")
async def list_users(user: UserContext = Depends(require_any_role("super_admin"))):
    """列出所有用户"""
    from app.config import get_settings
    if not get_settings().database_enabled:
        return {"users": [{"user_id": "demo-user", "username": "admin", "role": "park_manager"}]}

    from app.database.session import SessionLocal
    from app.database.models.rbac import User, UserRole, Role
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()
        user_list = []
        for u in users:
            role_result = await db.execute(
                select(Role.name).join(UserRole).where(UserRole.user_id == u.user_id)
            )
            role_name = role_result.scalar_one_or_none() or "viewer"
            user_list.append({
                "user_id": u.user_id,
                "username": u.username,
                "display_name": u.display_name,
                "role": role_name,
                "park_id": u.park_id,
            })
        return {"users": user_list}


@router.post("/admin/users")
async def create_user(body: dict, user: UserContext = Depends(require_any_role("super_admin"))):
    """创建新用户"""
    from app.config import get_settings
    if not get_settings().database_enabled:
        raise HTTPException(503, "Database not available")

    from uuid import uuid4
    from app.database.session import SessionLocal
    from app.database.models.rbac import User, Role, UserRole
    from app.core.security import hash_password
    from sqlalchemy import select

    async with SessionLocal() as db:
        user_id = str(uuid4())
        db.add(User(
            user_id=user_id,
            username=body["username"],
            password_hash=hash_password(body.get("password", "123456")),
            display_name=body.get("display_name", body["username"]),
            park_id=body.get("park_id"),
        ))
        # Assign role
        role_name = body.get("role", "viewer")
        role_result = await db.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if role:
            db.add(UserRole(user_id=user_id, role_id=role.role_id))
        await db.commit()
        return {"user_id": user_id, "username": body["username"], "role": role_name}
