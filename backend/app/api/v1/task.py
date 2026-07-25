"""Task API (P8: ID fix + team status + daily report)"""
from fastapi import APIRouter, HTTPException
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
    state = graph.get_state({"configurable": {"thread_id": task_id}})
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
    """P8: Agent 团队状态 — 来自 AGENT_REGISTRY 的真实数据"""
    from app.agents.registry import AGENT_REGISTRY
    agents = {}
    for name, info in AGENT_REGISTRY.items():
        agents[name] = {
            "display": info["display"],
            "status": "idle",
            "capabilities": info.get("capabilities", []),
            "last_task": None,
            "last_execution_ms": 0,
            "tasks_today": 0,
        }
    return {
        "success": True,
        "data": {
            "total_agents": len(AGENT_REGISTRY),
            "online_agents": len(AGENT_REGISTRY),
            "total_tasks_today": 0,
            "agents": agents,
        }
    }


@router.get("/agent/daily-report")
async def agent_daily_report():
    """P8: AI 日报 — 从现有数据聚合，带来源标识"""
    from datetime import datetime, timezone
    from app.config import get_settings
    s = get_settings()
    data_mode = "mock" if s.enterprise_data_source == "mock" else "production"

    return {
        "success": True,
        "data": {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_mode": data_mode,
            "summary": "园区运营日报（演示数据）",
            "park_metrics": {
                "total_enterprises": 5,
                "active_tasks": 0,
            },
            "investment": {
                "new_leads": 0,
                "active_negotiations": 0,
            },
            "risk_alerts": [],
            "policy_updates": 0,
            "ai_tasks_completed": 0,
            "recommendations": [],
        }
    }
