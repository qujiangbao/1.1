"""Stream Executor — P3 后台 graph 执行 + 事件发布

职责:
  - 在后台执行 graph.ainvoke()，不阻塞 HTTP 响应
  - 通过 EventBus 发布 done/error 事件
  - 通过 DatabaseTool 持久化结果

约束:
  - 不直接访问数据库 (通过 DatabaseTool)
  - 不放入 langgraph 目录"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def execute_graph_with_events(
    graph,
    state: dict,
    config: dict,
    task_id: str,
    conversation_id: str,
    db_tool,
    user_message: str,
) -> None:
    """后台执行 Supervisor graph 并通过 EventBus 发布完成事件

    Args:
        graph: 编译后的 StateGraph
        state: SupervisorState
        config: {"configurable": {"thread_id": "..."}}
        task_id: 任务 ID (用于 SSE 订阅 + DB 写入)
        conversation_id: 对话 ID
        db_tool: DatabaseTool 实例
        user_message: 原始用户消息
    """
    from app.services.event_bus import get_event_bus

    event_bus = get_event_bus()
    await event_bus.create_channel(task_id)

    try:
        result = await graph.ainvoke(state, config)

        response_text = result.get("final_response", "")
        agents_used = list(result.get("agent_results", {}).keys())

        # 发布 done 事件
        await event_bus.publish(task_id, "done", {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "status": result.get("status", "completed"),
            "final_response": response_text,
            "agents_used": agents_used,
            "trace_id": result.get("trace_id", ""),
            "intent": result.get("intent"),
        })

        # 持久化 agent_task
        try:
            await db_tool.save_agent_task({
                "task_id": task_id,
                "conversation_id": conversation_id,
                "user_id": state.get("user_id", "demo-user"),
                "intent": result.get("intent", ""),
                "goal": user_message,
                "priority": "medium",
                "plan": {"task_plan": result.get("task_plan", [])},
                "status": result.get("status", "completed"),
                "result": {"response": response_text, "agents_used": agents_used},
            })
        except Exception as e:
            logger.warning("[StreamExecutor] save_agent_task failed: %s", e)

        # 持久化对话消息
        try:
            await db_tool.save_message(conversation_id, "user", user_message)
            if response_text:
                await db_tool.save_message(conversation_id, "assistant", response_text[:2000])
        except Exception as e:
            logger.warning("[StreamExecutor] save_message failed: %s", e)

    except Exception as e:
        logger.exception("[StreamExecutor] graph execution failed: %s", e)
        await event_bus.publish(task_id, "error", {
            "task_id": task_id,
            "message": str(e),
        }, source="supervisor")

    # 不在此关闭 channel — SSE 端点负责关闭
