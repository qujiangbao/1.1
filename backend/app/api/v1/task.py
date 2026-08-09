"""Task API (P8: ID fix + team status + daily report)"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from app.schemas.agent import ChatRequest

router = APIRouter()


@router.post("/agent/task")
async def create_task(request: ChatRequest):
    from app.api.v1.agent import agent_chat
    return await agent_chat(request)


@router.get("/agent/task/{task_id}")
async def get_task(task_id: str):
    from app.langgraph.graph import get_supervisor_graph
    graph = await get_supervisor_graph()
    # P8: thread_id now uses task_id (not conversation_id)
    state = await graph.aget_state({"configurable": {"thread_id": task_id}})
    if state is None or not state.values:
        raise HTTPException(status_code=404, detail="Task not found")
    values = state.values
    return {
        "task_id": task_id,
        "status": values.get("status", "unknown"),
        "intent": values.get("intent"),
        "agents_used": list(values.get("agent_results", {}).keys()),
        "completed_at": values.get("completed_at"),
    }


@router.get("/agent/status")
async def agent_status():
    from app.agents.registry import AGENT_REGISTRY
    return {
        "total_agents": len(AGENT_REGISTRY),
        "agents": {name: {"display": info["display"], "capabilities": info["capabilities"]}
                   for name, info in AGENT_REGISTRY.items()}
    }


@router.get("/agent/team/status")
async def agent_team_status():
    """Return live state and today's durable execution metrics."""
    from app.services.dashboard_service import get_team_status

    return {
        "success": True,
        "data": await get_team_status(),
    }


@router.get("/agent/daily-report")
async def agent_daily_report(
    mode: Literal["real", "demo"] = Query(default="real"),
):
    """Return today's public-snapshot or isolated demo metrics."""
    from app.services.dashboard_service import get_daily_report
    return {
        "success": True,
        "data": await get_daily_report(mode=mode),
    }
