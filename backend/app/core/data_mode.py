"""Data-mode policy shared by public API endpoints."""

from fastapi import HTTPException

from app.config import get_settings


def require_allowed_data_mode(value: str | None) -> str:
    """Reject synthetic data unless it is explicitly enabled outside production."""

    normalized = str(value or "real").strip().lower()
    if normalized != "demo":
        return "real"
    settings = get_settings()
    if settings.app_env.lower() == "production" or not settings.enable_demo_mode:
        raise HTTPException(
            status_code=403,
            detail="演示数据模式在当前部署中已禁用",
        )
    return "demo"
