"""Administrative user management API (super administrators only)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.permissions import require_any_role
from app.core.security import UserContext


router = APIRouter()


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=200)
    role: str = Field(default="viewer", max_length=50)
    park_id: str | None = Field(default=None, max_length=50)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=50)
    park_id: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


async def _role_name(db, user_id: str) -> str:
    from app.database.models.rbac import Role, UserRole
    from sqlalchemy import select

    result = await db.execute(
        select(Role.name).join(UserRole).where(UserRole.user_id == user_id)
    )
    return result.scalar_one_or_none() or "viewer"


async def _active_super_admin_count(db) -> int:
    from app.database.models.rbac import Role, User, UserRole
    from sqlalchemy import func, select

    result = await db.execute(
        select(func.count(User.user_id))
        .select_from(User)
        .join(UserRole, UserRole.user_id == User.user_id)
        .join(Role, Role.role_id == UserRole.role_id)
        .where(Role.name == "super_admin", User.is_active.is_(True))
    )
    return int(result.scalar_one() or 0)


def _serialize_user(account, role_name: str) -> dict:
    return {
        "user_id": account.user_id,
        "username": account.username,
        "display_name": account.display_name,
        "role": role_name,
        "park_id": account.park_id,
        "is_active": account.is_active,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


@router.get("/admin/users")
async def list_users(
    user: UserContext = Depends(require_any_role("super_admin")),
):
    """List every managed account."""
    from app.config import get_settings

    if not get_settings().database_enabled:
        return {
            "users": [
                {
                    "user_id": "demo-user",
                    "username": "admin",
                    "display_name": "系统管理员",
                    "role": "super_admin",
                    "park_id": None,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                }
            ]
        }

    from app.database.models.rbac import User
    from app.database.session import SessionLocal
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(User).order_by(User.created_at.asc()))
        users = result.scalars().all()
        return {
            "users": [
                _serialize_user(account, await _role_name(db, account.user_id))
                for account in users
            ]
        }


@router.post("/admin/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    user: UserContext = Depends(require_any_role("super_admin")),
):
    """Create an account and assign one role."""
    from app.config import get_settings

    if not get_settings().database_enabled:
        raise HTTPException(503, "Database not available")

    from uuid import uuid4

    from app.core.security import hash_password
    from app.database.models.rbac import Role, User, UserRole
    from app.database.session import SessionLocal
    from sqlalchemy import select

    async with SessionLocal() as db:
        duplicate = await db.execute(select(User).where(User.username == body.username))
        if duplicate.scalar_one_or_none() is not None:
            raise HTTPException(409, "Username already exists")

        role = (
            await db.execute(select(Role).where(Role.name == body.role))
        ).scalar_one_or_none()
        if role is None:
            raise HTTPException(422, "Role not found")

        account = User(
            user_id=str(uuid4()),
            username=body.username,
            password_hash=hash_password(body.password),
            display_name=body.display_name or body.username,
            park_id=body.park_id,
        )
        db.add(account)
        await db.flush()
        db.add(UserRole(user_id=account.user_id, role_id=role.role_id))
        await db.commit()
        await db.refresh(account)
        return _serialize_user(account, role.name)


@router.patch("/admin/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    actor: UserContext = Depends(require_any_role("super_admin")),
):
    """Edit account details, role, status, or reset its password."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.database_enabled:
        raise HTTPException(503, "Database not available")

    from app.core.security import hash_password
    from app.database.models.rbac import Role, User, UserRole
    from app.database.session import SessionLocal
    from sqlalchemy import delete, select

    async with SessionLocal() as db:
        account = await db.get(User, user_id)
        if account is None:
            raise HTTPException(404, "User not found")

        fields = body.model_dump(exclude_unset=True)
        current_role = await _role_name(db, account.user_id)
        is_current = actor.user_id == account.user_id
        is_bootstrap = (
            account.user_id == "user-admin-001"
            or account.username == settings.admin_username
        )

        protected_self_fields = {"username", "password", "role", "is_active"}
        if is_current and protected_self_fields.intersection(fields):
            raise HTTPException(
                409,
                "Current account security settings cannot be changed here",
            )
        if is_bootstrap and protected_self_fields.intersection(fields):
            raise HTTPException(
                409,
                "Bootstrap administrator security settings are protected",
            )

        losing_super_admin = (
            current_role == "super_admin"
            and account.is_active
            and (
                (body.role is not None and body.role != "super_admin")
                or fields.get("is_active") is False
            )
        )
        if losing_super_admin and await _active_super_admin_count(db) <= 1:
            raise HTTPException(409, "At least one active super administrator is required")

        if "username" in fields and fields["username"] != account.username:
            duplicate = await db.execute(
                select(User).where(User.username == fields["username"])
            )
            if duplicate.scalar_one_or_none() is not None:
                raise HTTPException(409, "Username already exists")
            account.username = fields["username"]

        if "password" in fields:
            account.password_hash = hash_password(fields["password"])

        for field in ("display_name", "park_id", "is_active"):
            if field in fields:
                setattr(account, field, fields[field])

        next_role = current_role
        if body.role is not None and body.role != current_role:
            role = (
                await db.execute(select(Role).where(Role.name == body.role))
            ).scalar_one_or_none()
            if role is None:
                raise HTTPException(422, "Role not found")
            await db.execute(delete(UserRole).where(UserRole.user_id == account.user_id))
            db.add(UserRole(user_id=account.user_id, role_id=role.role_id))
            next_role = role.name

        await db.commit()
        await db.refresh(account)
        return _serialize_user(account, next_role)


@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    actor: UserContext = Depends(require_any_role("super_admin")),
):
    """Delete an account while preserving administrator safety invariants."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.database_enabled:
        raise HTTPException(503, "Database not available")

    from app.database.models.rbac import User, UserRole
    from app.database.session import SessionLocal
    from sqlalchemy import delete

    async with SessionLocal() as db:
        account = await db.get(User, user_id)
        if account is None:
            raise HTTPException(404, "User not found")
        if actor.user_id == account.user_id:
            raise HTTPException(409, "Cannot delete the current account")
        if account.user_id == "user-admin-001" or account.username == settings.admin_username:
            raise HTTPException(409, "The bootstrap administrator cannot be deleted")

        role_name = await _role_name(db, account.user_id)
        if (
            role_name == "super_admin"
            and account.is_active
            and await _active_super_admin_count(db) <= 1
        ):
            raise HTTPException(409, "At least one active super administrator is required")

        await db.execute(delete(UserRole).where(UserRole.user_id == account.user_id))
        await db.delete(account)
        await db.commit()
        return {"ok": True, "deleted_user_id": user_id}
