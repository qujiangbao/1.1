"""Regression tests for fail-closed authentication and object ownership."""

import pytest
from fastapi import HTTPException

from app.core import security
from app.core.permissions import require_permission
from app.core.security import UserContext, create_access_token, require_task_owner


@pytest.mark.asyncio
async def test_database_enabled_rejects_missing_or_disabled_user(monkeypatch):
    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "database_enabled", True)

    async def missing_user(_user_id: str):
        return None

    monkeypatch.setattr(security, "_get_user_from_db", missing_user)
    token = create_access_token({"sub": "disabled", "role": "super_admin"})

    with pytest.raises(HTTPException) as exc_info:
        await security.require_user(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_database_failure_does_not_fall_back_to_jwt_claims(monkeypatch):
    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "database_enabled", True)

    async def unavailable(_user_id: str):
        raise RuntimeError("database offline")

    monkeypatch.setattr(security, "_get_user_from_db", unavailable)
    token = create_access_token({"sub": "user-1", "role": "super_admin"})

    with pytest.raises(HTTPException) as exc_info:
        await security.require_user(token)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_database_role_overrides_stale_privileged_claim(monkeypatch):
    monkeypatch.setattr(security.settings, "auth_enabled", True)
    monkeypatch.setattr(security.settings, "database_enabled", True)

    async def current_user(_user_id: str):
        return {
            "user_id": "user-1",
            "username": "viewer",
            "role": "viewer",
            "park_id": "park-1",
            "display_name": "Viewer",
        }

    monkeypatch.setattr(security, "_get_user_from_db", current_user)
    token = create_access_token({"sub": "user-1", "role": "super_admin"})

    user = await security.require_user(token)

    assert user.role == "viewer"


def test_task_owner_check_hides_other_users_tasks(monkeypatch):
    monkeypatch.setattr(security.settings, "auth_enabled", True)
    user = UserContext(user_id="user-1", username="one", role="viewer")

    with pytest.raises(HTTPException) as exc_info:
        require_task_owner({"user_id": "user-2"}, user)

    assert exc_info.value.status_code == 404
    require_task_owner({"user_id": "user-1"}, user)


def test_super_admin_can_inspect_any_task(monkeypatch):
    monkeypatch.setattr(security.settings, "auth_enabled", True)
    admin = UserContext(user_id="admin", username="admin", role="super_admin")

    require_task_owner({"user_id": "user-2"}, admin)


@pytest.mark.asyncio
async def test_permission_check_uses_role_map_without_database(monkeypatch):
    monkeypatch.setattr(security.settings, "database_enabled", False)
    viewer = UserContext(user_id="viewer", username="viewer", role="viewer")
    admin = UserContext(user_id="admin", username="admin", role="super_admin")

    with pytest.raises(HTTPException) as exc_info:
        await require_permission("api:admin")(viewer)

    assert exc_info.value.status_code == 403
    assert await require_permission("api:admin")(admin) is admin


@pytest.mark.asyncio
async def test_permission_database_failure_is_unavailable(monkeypatch):
    monkeypatch.setattr(security.settings, "database_enabled", True)
    viewer = UserContext(user_id="viewer", username="viewer", role="viewer")

    with pytest.raises(HTTPException) as exc_info:
        await require_permission("api:dashboard")(viewer)

    assert exc_info.value.status_code == 503
