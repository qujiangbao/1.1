"""Dashboard API"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard/kpi")
async def dashboard_kpi():
    return {"success": True, "data": {
        "park_overview": {"total_enterprises": 12580, "growth_rate": "3.2%"},
        "investment": {"opportunities": 230, "conversion_rate": "5.2%"},
    }}
