from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.config import get_settings

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def authenticate_admin(username: str, password: str) -> bool:
    """Constant-time comparison for the configurable demo administrator."""
    return compare_digest(username, settings.admin_username) and compare_digest(
        password, settings.admin_password
    )


async def require_user(token: Annotated[str | None, Depends(oauth2_scheme)]) -> dict:
    if not settings.auth_enabled:
        return {"sub": "demo-user", "role": "park_manager"}
    payload = verify_token(token) if token else None
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
