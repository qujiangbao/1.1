"""Task API"""
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
    state = get_supervisor_graph().get_state({"configurable": {"thread_id": task_id}})
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
