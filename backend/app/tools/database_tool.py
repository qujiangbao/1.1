"""DatabaseTool — Agent 状态持久化工具 (P2)

映射到现有 Database Architecture V1.0 五表:
  - conversation   (Conversation)  → 对话元数据 + thread_id
  - agent_memory   (AgentMemory)   → 多轮对话消息
  - agent_task     (AgentTask)     → 任务生命周期
  - agent_execution(AgentExecution)→ Agent 执行记录
  - agent_trace    (AgentTrace)    → 每步 trace

设计原则:
  - 异步方法（API 层在 graph 调用前后使用）
  - database_enabled=false 时所有方法静默跳过
  - 仅 Supervisor 可访问（通过 ToolGateway 权限控制）"""

import logging
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DatabaseTool:
    """数据库持久化工具 — 唯一数据访问通道"""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    async def _db(self):
        """获取异步 session"""
        from app.database.session import SessionLocal
        if SessionLocal is None:
            raise RuntimeError("Database is not initialized")
        async with SessionLocal() as session:
            yield session

    # ── Conversation ──

    async def save_conversation(self, conv_id: str, user_id: str = "",
                                title: str = "", thread_id: str = "") -> None:
        """Upsert conversation 元数据"""
        if not self.enabled:
            return
        try:
            from app.database.models.runtime import Conversation
            async for db in self._db():
                from sqlalchemy import select
                result = await db.execute(
                    select(Conversation).where(Conversation.conversation_id == conv_id)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.title = title or existing.title
                    existing.thread_id = thread_id or existing.thread_id
                    existing.message_count = (existing.message_count or 0) + 1
                    existing.last_message_at = datetime.now(timezone.utc)
                    existing.updated_time = datetime.now(timezone.utc)
                else:
                    conv = Conversation(
                        conversation_id=conv_id,
                        user_id=user_id,
                        title=title,
                        thread_id=thread_id,
                        message_count=1,
                        last_message_at=datetime.now(timezone.utc),
                    )
                    db.add(conv)
                await db.commit()
        except Exception as e:
            logger.warning("save_conversation(%s) failed: %s", conv_id, e)

    async def load_conversation_history(self, conv_id: str,
                                        limit: int = 10) -> List[Dict[str, Any]]:
        """加载 agent_memory 表中最近 N 轮对话消息"""
        if not self.enabled:
            return []
        try:
            from app.database.models.runtime import AgentMemory
            async for db in self._db():
                from sqlalchemy import select
                result = await db.execute(
                    select(AgentMemory)
                    .where(AgentMemory.conversation_id == conv_id)
                    .order_by(AgentMemory.created_at.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                return [
                    {"role": r.role, "content": r.content,
                     "timestamp": r.created_at.isoformat() if r.created_at else ""}
                    for r in reversed(rows)  # 正序返回
                ]
        except Exception as e:
            logger.warning("load_conversation_history(%s) failed: %s", conv_id, e)
            return []

    async def save_message(self, conv_id: str, role: str,
                           content: str, metadata: Dict = None) -> None:
        """写入 agent_memory 表"""
        if not self.enabled:
            return
        try:
            from app.database.models.runtime import AgentMemory
            async for db in self._db():
                mem = AgentMemory(
                    memory_id=str(uuid4()),
                    conversation_id=conv_id,
                    role=role,
                    content=content,
                    metadata_=metadata or {},
                )
                db.add(mem)
                await db.commit()
        except Exception as e:
            logger.warning("save_message(%s) failed: %s", conv_id, e)

    # ── Agent Task ──

    async def save_agent_task(self, task: Dict[str, Any]) -> None:
        """Upsert agent_task 记录"""
        if not self.enabled:
            return
        try:
            from app.database.models.runtime import AgentTask
            async for db in self._db():
                from sqlalchemy import select
                tid = task.get("task_id", "")
                result = await db.execute(
                    select(AgentTask).where(AgentTask.task_id == tid)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.status = task.get("status", existing.status)
                    existing.result = task.get("result")
                    existing.plan = task.get("plan")
                    existing.completed_time = datetime.now(timezone.utc)
                else:
                    at = AgentTask(
                        task_id=tid,
                        conversation_id=task.get("conversation_id", ""),
                        user_id=task.get("user_id", ""),
                        intent=task.get("intent", ""),
                        goal=task.get("goal", ""),
                        priority=task.get("priority", "medium"),
                        plan=task.get("plan"),
                        status=task.get("status", "created"),
                        result=task.get("result"),
                    )
                    db.add(at)
                await db.commit()
        except Exception as e:
            logger.warning("save_agent_task(%s) failed: %s", task.get("task_id"), e)

    async def load_agent_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """加载 agent_task 记录"""
        if not self.enabled:
            return None
        try:
            from app.database.models.runtime import AgentTask
            async for db in self._db():
                from sqlalchemy import select
                result = await db.execute(
                    select(AgentTask).where(AgentTask.task_id == task_id)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return None
                return {
                    "task_id": row.task_id,
                    "conversation_id": row.conversation_id,
                    "intent": row.intent,
                    "goal": row.goal,
                    "status": row.status,
                    "plan": row.plan,
                    "result": row.result,
                    "created_time": row.created_time.isoformat() if row.created_time else None,
                    "completed_time": row.completed_time.isoformat() if row.completed_time else None,
                }
        except Exception as e:
            logger.warning("load_agent_task(%s) failed: %s", task_id, e)
            return None

    # ── Agent Execution ──

    async def save_agent_execution(self, execution: Dict[str, Any]) -> None:
        """写入 agent_execution 记录"""
        if not self.enabled:
            return
        try:
            from app.database.models.runtime import AgentExecution
            async for db in self._db():
                ae = AgentExecution(
                    execution_id=execution.get("execution_id", str(uuid4())),
                    task_id=execution.get("task_id", ""),
                    agent_name=execution.get("agent_name", ""),
                    order_num=execution.get("order_num", 0),
                    input=execution.get("input"),
                    output=execution.get("output"),
                    status=execution.get("status", ""),
                    start_time=execution.get("start_time"),
                    end_time=execution.get("end_time"),
                    duration_ms=execution.get("duration_ms", 0),
                    error=execution.get("error"),
                )
                db.add(ae)
                await db.commit()
        except Exception as e:
            logger.warning("save_agent_execution failed: %s", e)

    # ── Agent Trace ──

    async def save_agent_trace(self, trace: Dict[str, Any]) -> None:
        """写入 agent_trace 记录"""
        if not self.enabled:
            return
        try:
            from app.database.models.runtime import AgentTrace
            async for db in self._db():
                at = AgentTrace(
                    trace_id=trace.get("trace_id", str(uuid4())),
                    task_id=trace.get("task_id", ""),
                    step=trace.get("step", 0),
                    type=trace.get("type", ""),
                    agent_name=trace.get("agent_name", ""),
                    action=trace.get("action", ""),
                    input=trace.get("input"),
                    output=trace.get("output"),
                    source=trace.get("source", ""),
                    duration_ms=trace.get("duration_ms", 0),
                )
                db.add(at)
                await db.commit()
        except Exception as e:
            logger.warning("save_agent_trace failed: %s", e)

    # ── Checkpoint Status (读取 LangGraph 自动管理的 checkpoints 表) ──

    async def get_checkpoint_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """读取 LangGraph checkpoints 表的最新 checkpoint 状态"""
        if not self.enabled:
            return {"thread_id": thread_id, "status": "not_found",
                    "note": "Database disabled — using MemorySaver"}
        try:
            async for db in self._db():
                from sqlalchemy import text
                result = await db.execute(
                    text("""
                        SELECT checkpoint_id, metadata, checkpoint
                        FROM checkpoints
                        WHERE thread_id = :tid
                        ORDER BY checkpoint_id DESC
                        LIMIT 1
                    """),
                    {"tid": thread_id},
                )
                row = result.fetchone()
                if row is None:
                    return {"thread_id": thread_id, "status": "not_found"}

                import json
                metadata = json.loads(row[1]) if row[1] else {}
                checkpoint_data = json.loads(row[2]) if row[2] else {}

                # Extract state from checkpoint blob
                channels = checkpoint_data.get("channel_values", {})
                status = channels.get("status", "unknown")
                current_node = metadata.get("step", -1)

                # Map step number to node name
                node_names = ["user_input", "intent_recognition", "task_planner",
                              "agent_router", "result_validator", "result_aggregator",
                              "finalize_response"]
                node_name = node_names[current_node] if 0 <= current_node < len(node_names) else None

                return {
                    "thread_id": thread_id,
                    "checkpoint_id": row[0],
                    "status": status,
                    "current_node": node_name,
                    "completed_nodes": current_node + 1 if current_node >= 0 else 0,
                    "total_nodes": 7,
                    "task_plan": channels.get("task_plan", []),
                    "last_checkpoint_at": metadata.get("timestamp", ""),
                }
        except Exception as e:
            logger.warning("get_checkpoint_status(%s) failed: %s", thread_id, e)
            return {"thread_id": thread_id, "status": "error", "error": str(e)}

    # ── Health ──

    async def health_check(self) -> bool:
        """数据库连通性检查"""
        if not self.enabled:
            return False
        try:
            async for db in self._db():
                from sqlalchemy import text
                await db.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.warning("Database health check failed: %s", e)
            return False


# 全局单例
_db_tool: Optional[DatabaseTool] = None


def get_database_tool() -> DatabaseTool:
    global _db_tool
    if _db_tool is None:
        from app.config import get_settings
        _db_tool = DatabaseTool(enabled=get_settings().database_enabled)
    return _db_tool
