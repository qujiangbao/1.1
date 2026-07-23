"""Agent Chat API — 用户对话核心入口"""
from fastapi import APIRouter
from app.schemas.agent import ChatRequest, ChatResponse
from app.langgraph.graph import get_supervisor_graph
from uuid import uuid4
import time

router = APIRouter()


@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    """用户对话入口：接受自然语言 → Supervisor → Agent → 返回结果"""
    conversation_id = request.conversation_id or str(uuid4())
    task_id = str(uuid4())
    started = time.perf_counter()
    
    graph = get_supervisor_graph()
    state = {
        "user_id": "demo-user",
        "conversation_id": conversation_id,
        "user_query": request.message,
        "user_role": "park_manager",
        "messages": [],
        "status": "idle",
        "trace_id": str(uuid4()),
    }
    
    config = {"configurable": {"thread_id": task_id}}
    result = await graph.ainvoke(state, config)
    
    return ChatResponse(
        task_id=task_id,
        conversation_id=conversation_id,
        status=result.get("status", "completed"),
        response=result.get("final_response", ""),
        agents_used=list(result.get("agent_results", {}).keys()),
        trace_id=result.get("trace_id", ""),
        execution_time_ms=max(1, int((time.perf_counter() - started) * 1000)),
    )
