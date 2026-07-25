"""Agent Chat API — 用户对话核心入口 (P3: Streaming Support)"""
import asyncio
import time
from uuid import uuid4
from fastapi import APIRouter
from app.schemas.agent import ChatRequest, ChatResponse, CheckpointStatus
from app.langgraph.graph import get_supervisor_graph

router = APIRouter()


@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    """用户对话入口：接受自然语言 → Supervisor → Agent → 返回结果

    P3 双模式:
      - streaming_enabled=true  → 异步执行, 立即返回 task_id + stream_url
      - streaming_enabled=false → 同步执行 (v1.2 行为, 100% 兼容)
    """
    import logging
    logger = logging.getLogger(__name__)

    conversation_id = request.conversation_id or str(uuid4())
    task_id = str(uuid4())
    started = time.perf_counter()

    # P2: DB tool + 对话历史
    from app.tools.database_tool import get_database_tool
    db_tool = get_database_tool()
    history = await db_tool.load_conversation_history(conversation_id)

    await db_tool.save_conversation(
        conv_id=conversation_id,
        user_id=request.context.get("user_id", "demo-user") if request.context else "demo-user",
        title=request.message[:50],
        thread_id=conversation_id,
    )

    graph = await get_supervisor_graph()
    state = {
        "user_id": request.context.get("user_id", "demo-user") if request.context else "demo-user",
        "conversation_id": conversation_id,
        "user_query": request.message,
        "user_role": "park_manager",
        "messages": [],
        "history_messages": history,
        "status": "idle",
        "trace_id": task_id,  # P3: trace_id = task_id (SSE 订阅 key)
    }
    config = {"configurable": {"thread_id": conversation_id}}

    from app.config import get_settings
    settings = get_settings()

    # === P3 分支: 异步流式执行 ===
    if settings.streaming_enabled:
        from app.services.stream_executor import execute_graph_with_events
        asyncio.create_task(execute_graph_with_events(
            graph, state, config, task_id, conversation_id, db_tool, request.message,
        ))
        logger.info("[P3] Streaming task started: %s", task_id)
        return ChatResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            status="processing",
            response=None,
            stream_url=f"/api/v1/agent/stream/{task_id}",
        )

    # === v1.2 兼容: 同步执行 ===
    result = await graph.ainvoke(state, config)

    response_text = result.get("final_response", "")
    agents_used = list(result.get("agent_results", {}).keys())

    # P2: 持久化
    await db_tool.save_agent_task({
        "task_id": task_id,
        "conversation_id": conversation_id,
        "user_id": state["user_id"],
        "intent": result.get("intent", ""),
        "goal": request.message,
        "priority": "medium",
        "plan": {"task_plan": result.get("task_plan", [])},
        "status": result.get("status", "completed"),
        "result": {"response": response_text, "agents_used": agents_used},
    })

    await db_tool.save_message(conversation_id, "user", request.message)
    if response_text:
        await db_tool.save_message(conversation_id, "assistant", response_text[:2000])

    return ChatResponse(
        task_id=task_id,
        conversation_id=conversation_id,
        status=result.get("status", "completed"),
        response=response_text,
        agents_used=agents_used,
        trace_id=result.get("trace_id", ""),
        execution_time_ms=max(1, int((time.perf_counter() - started) * 1000)),
    )


@router.get("/agent/checkpoint/{thread_id}", response_model=CheckpointStatus)
async def get_checkpoint_status(thread_id: str):
    """查询 Agent 执行进度（从 LangGraph checkpoints 表读取）

    DATABASE_ENABLED=true  → 从 PostgreSQL checkpoints 表读取
    DATABASE_ENABLED=false → 返回 not_found + 提示
    """
    from app.tools.database_tool import get_database_tool
    db_tool = get_database_tool()
    status = await db_tool.get_checkpoint_status(thread_id)
    if status is None:
        return CheckpointStatus(
            thread_id=thread_id,
            status="not_found",
        )
    return CheckpointStatus(**status)
