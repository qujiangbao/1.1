"""Stream API — P3 SSE 实时事件流端点

GET /agent/stream/{task_id}          — SSE 事件流
GET /agent/stream/{task_id}/snapshot — 当前任务状态快照"""

import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/agent/stream/{task_id}")
async def agent_stream(task_id: str):
    """SSE 端点 — 订阅 Agent 执行实时事件流

    行为:
      - STREAMING_ENABLED=true  → 返回 SSE text/event-stream
      - STREAMING_ENABLED=false → 返回 404
      - 首次连接: 检查是否有已完成状态 → 发送 snapshot
      - 运行时: 转发 EventBus 事件 (经 EventNormalizer 标准化)
      - 心跳: 每 streaming_heartbeat_seconds 秒发送
      - done/error 事件 → 关闭连接
    """
    from app.config import get_settings
    settings = get_settings()
    if not settings.streaming_enabled:
        raise HTTPException(status_code=404, detail="Streaming is disabled")

    from app.services.event_bus import get_event_bus
    from app.services.event_normalizer import EventNormalizer

    event_bus = get_event_bus()
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    await event_bus.subscribe(task_id, queue)

    heartbeat_sec = settings.streaming_heartbeat_seconds

    async def generate():
        try:
            # Step 1: 尝试发送 snapshot（重连场景）
            snapshot = await _build_snapshot(task_id)
            if snapshot:
                yield _sse_frame("snapshot", snapshot)

            # Step 2: 转发实时事件
            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=heartbeat_sec)
                    if raw is None:  # channel 关闭信号
                        break
                    normalized = EventNormalizer.normalize(raw)
                    yield _sse_frame(normalized["event_type"], normalized)
                    if raw["event_type"] in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    yield _sse_frame("heartbeat", {})
        finally:
            await event_bus.unsubscribe(task_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agent/stream/{task_id}/snapshot")
async def agent_stream_snapshot(task_id: str):
    """获取当前任务状态快照 (用于初始加载或轮询降级)"""
    snapshot = await _build_snapshot(task_id)
    if snapshot is None:
        return {"task_id": task_id, "status": "not_found"}
    return snapshot


def _sse_frame(event_type: str, data: dict) -> str:
    """构建 SSE frame"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _build_snapshot(task_id: str) -> dict | None:
    """从 LangGraph state 构建当前进度快照"""
    try:
        from app.langgraph.graph import get_supervisor_graph
        graph = await get_supervisor_graph()
        state = graph.get_state({"configurable": {"thread_id": task_id}})
        if state is None or not state.values:
            return None

        sv = state.values
        task_plan_summary = [
            {
                "task_id": t.get("task_id", ""),
                "agent": t.get("agent", ""),
                "status": t.get("status", ""),
                "intent": t.get("intent", ""),
            }
            for t in sv.get("task_plan", [])
        ]

        agent_summaries = {}
        for agent, ar in sv.get("agent_results", {}).items():
            agent_summaries[agent] = {
                "status": ar.get("status", "unknown"),
                "summary": (ar.get("result") or {}).get("summary", "")[:200],
                "execution_time_ms": ar.get("execution_time_ms", 0),
            }

        return {
            "task_id": task_id,
            "conversation_id": sv.get("conversation_id", ""),
            "status": sv.get("status", "unknown"),
            "intent": sv.get("intent"),
            "intents": sv.get("intents", []),
            "task_plan": task_plan_summary,
            "agent_results": agent_summaries,
            "started_at": sv.get("started_at"),
            "completed_at": sv.get("completed_at"),
        }
    except Exception as e:
        logger.warning("[Stream] snapshot build failed: %s", e)
        return None
