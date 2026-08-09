"""Security - JWT authentication and task ownership checks."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import InvalidTokenError
from app.config import get_settings

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """从 JWT 解析的用户上下文，注入到 request.state"""
    user_id: str = "demo-user"
    username: str = "demo"
    role: str = "park_manager"
    park_id: Optional[str] = None
    display_name: Optional[str] = None


# ═══ Token 生成/验证 ═══

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """生成 Access Token (短期, 默认 24h)"""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """生成 Refresh Token (长期, 30d)"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=30)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": expire, "type": "refresh"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_stream_token(task_id: str, user_id: str, expires_minutes: int = 10) -> str:
    """Create a short-lived token scoped to one Agent SSE task.

    Browser ``EventSource`` cannot attach the normal Authorization header. A
    task-scoped token keeps the stream usable without exposing other tasks.
    """
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "task_id": task_id,
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
            "type": "agent_stream",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str) -> dict | None:
    """验证并解码 JWT Token"""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError:
        return None


def verify_stream_token(token: str, task_id: str) -> bool:
    """Verify that a short-lived stream token belongs to ``task_id``."""
    payload = verify_token(token)
    if not payload or payload.get("type") != "agent_stream":
        return False
    token_task_id = str(payload.get("task_id", ""))
    return bool(token_task_id) and compare_digest(token_task_id, str(task_id))


def hash_password(password: str) -> str:
    """bcrypt 密码哈希 (P5: 升级自 SHA256)"""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码 (兼容 bcrypt + SHA256 legacy)"""
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Legacy SHA256 fallback
        import hashlib
        return compare_digest(
            hashlib.sha256(password.encode()).hexdigest(),
            password_hash,
        )


# ═══ FastAPI Dependencies ═══

async def _get_user_from_db(user_id: str) -> Optional[dict]:
    """从数据库加载用户信息"""
    from app.config import get_settings
    s = get_settings()
    if not s.database_enabled:
        return None
    try:
        from app.database.session import SessionLocal
        from app.database.models.rbac import User, UserRole, Role
        from sqlalchemy import select
        async with SessionLocal() as db:
            result = await db.execute(
                select(User).where(User.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            if user is None or not user.is_active:
                return None
            # Get role
            role_result = await db.execute(
                select(Role.name).join(UserRole).where(UserRole.user_id == user_id)
            )
            role_name = role_result.scalar_one_or_none() or "viewer"
            return {
                "user_id": user.user_id,
                "username": user.username,
                "role": role_name,
                "park_id": user.park_id,
                "display_name": user.display_name,
            }
    except Exception:
        logger.exception("Authentication database lookup failed for user_id=%s", user_id)
        raise


async def require_user(token: Annotated[str | None, Depends(oauth2_scheme)]) -> UserContext:
    """解析 JWT → UserContext (所有 API 的认证依赖)

    AUTH_ENABLED=false → 返回 demo-user (v1.2 兼容)
    AUTH_ENABLED=true  → 验证 JWT + 加载用户
    """
    if not settings.auth_enabled:
        return UserContext()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token type must be 'access'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]

    # The database is authoritative when enabled. Never trust stale JWT role
    # claims after an account is disabled, deleted, or downgraded.
    if settings.database_enabled:
        try:
            db_user = await _get_user_from_db(user_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication backend unavailable",
            ) from exc
        if db_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is unavailable or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return UserContext(**db_user)

    # Fallback: 使用 JWT payload 中的信息
    return UserContext(
        user_id=user_id,
        username=payload.get("username", user_id),
        role=payload.get("role", "viewer"),
        park_id=payload.get("park_id"),
    )


def require_task_owner(values: dict, user: UserContext) -> None:
    """Hide tasks owned by another user when authentication is enabled."""
    if not settings.auth_enabled or user.role == "super_admin":
        return
    owner_id = str(values.get("user_id") or "")
    if not owner_id or not compare_digest(owner_id, str(user.user_id)):
        raise HTTPException(status_code=404, detail="Task not found")
