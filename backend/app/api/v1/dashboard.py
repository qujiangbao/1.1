"""Dashboard API backed by public snapshots or an isolated demo scenario."""
from typing import Literal

from fastapi import APIRouter, Query

from app.services.dashboard_service import (
    get_bi_dashboard,
    get_dashboard_overview,
    get_risk_dashboard,
)
from app.core.data_mode import require_allowed_data_mode

router = APIRouter()


@router.get("/dashboard/kpi")
async def dashboard_kpi(mode: Literal["real", "demo"] = Query(default="real")):
    mode = require_allowed_data_mode(mode)
    overview = await get_dashboard_overview(mode=mode)
    return {
        "success": True,
        "data": {
            "park_overview": overview["park_overview"],
            "investment": overview["investment"],
            "risk": overview["risk"],
            "ai_operations": overview["ai_operations"],
            "metadata": overview["metadata"],
        },
    }


@router.get("/dashboard/overview")
async def dashboard_overview(
    mode: Literal["real", "demo"] = Query(default="real"),
):
    mode = require_allowed_data_mode(mode)
    return {"success": True, "data": await get_dashboard_overview(mode=mode)}


@router.get("/dashboard/bi")
async def dashboard_bi(mode: Literal["real", "demo"] = Query(default="real")):
    mode = require_allowed_data_mode(mode)
    return {"success": True, "data": await get_bi_dashboard(mode=mode)}


@router.get("/dashboard/risk")
async def dashboard_risk(
    limit: int = Query(default=50, ge=1, le=200),
    mode: Literal["real", "demo"] = Query(default="real"),
):
    mode = require_allowed_data_mode(mode)
    return {
        "success": True,
        "data": await get_risk_dashboard(limit=limit, mode=mode),
    }
