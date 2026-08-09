"""Supervisor LangGraph — 核心编排图 (P2: AsyncPostgresSaver)"""
import asyncio
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.langgraph.state import SupervisorState

logger = logging.getLogger(__name__)

# === Intent → Agent 路由表 ===
INTENT_ROUTING = {
    "investment_search":     "InvestmentAgent",
    "investment_profile":    "InvestmentAgent",
    "investment_scoring":    "InvestmentAgent",
    "investment_strategy":   "InvestmentAgent",
    "policy_query":          "PolicyAgent",
    "policy_match":          "PolicyAgent",
    "policy_recommend":      "PolicyAgent",
    "service_request":       "EnterpriseServiceAgent",
    "service_ticket":        "EnterpriseServiceAgent",
    "industry_analysis":     "IndustryAgent",
    "industry_trend":        "IndustryAgent",
    "industry_chain":        "IndustryAgent",
    "risk_single":           "RiskAgent",
    "risk_batch":            "RiskAgent",
    "risk_trend":            "RiskAgent",
    "dashboard_kpi":         "BIAgent",
    "dashboard_chart":       "BIAgent",
    "ai_insight":            "BIAgent",
}


def router(state: SupervisorState) -> str:
    """条件路由：决定下一个节点"""
    status = state.get("status", "idle")

    if status == "idle":
        return "intent_recognition"

    if state.get("intent") and not state.get("task_plan"):
        return "task_planner"

    if state.get("task_plan"):
        pending = [t for t in state["task_plan"] if t.get("status") == "pending"]
        if pending:
            ready = [
                t for t in pending
                if all(
                    any(
                        t2.get("task_id") == dep and t2.get("status") == "completed"
                        for t2 in state["task_plan"]
                    )
                    for dep in t.get("dependencies", [])
                )
            ]
            if ready:
                state["current_task_index"] = state["task_plan"].index(ready[0])
                return "agent_router"

    all_done = all(
        t.get("status") in ("completed", "failed")
        for t in state.get("task_plan", [])
    )
    if all_done and state.get("task_plan"):
        return "result_validator"

    if state.get("agent_results"):
        return "result_aggregator"

    if state.get("aggregated_result"):
        return "final_response"

    return END


def needs_approval(state: SupervisorState) -> str:
    """检查是否需要人工审批"""
    return "finalize_response"


def _build_workflow() -> StateGraph:
    """构建 Supervisor workflow（不含 checkpointer）"""
    from app.langgraph.nodes.supervisor_nodes import (
        user_input_node, intent_recognition_node, task_planner_node,
        agent_router_node, result_validator_node, result_aggregator_node,
        final_response_node,
    )

    workflow = StateGraph(SupervisorState)

    # 注册节点
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("task_planner", task_planner_node)
    workflow.add_node("agent_router", agent_router_node)
    workflow.add_node("result_validator", result_validator_node)
    workflow.add_node("result_aggregator", result_aggregator_node)
    workflow.add_node("finalize_response", final_response_node)

    workflow.set_entry_point("user_input")

    workflow.add_edge("user_input", "intent_recognition")
    workflow.add_edge("intent_recognition", "task_planner")
    workflow.add_edge("task_planner", "agent_router")

    workflow.add_conditional_edges("agent_router", router, {
        "agent_router": "agent_router",
        "result_validator": "result_validator",
        "result_aggregator": "result_aggregator",
        "final_response": "finalize_response",
        END: END,
    })

    workflow.add_edge("result_validator", "result_aggregator")
    workflow.add_conditional_edges("result_aggregator", needs_approval, {
        "finalize_response": "finalize_response",
    })
    workflow.add_edge("finalize_response", END)

    return workflow


# === 全局单例 (P2: 懒初始化 + AsyncPostgresSaver) ===
_supervisor_graph = None
_checkpointer = None
_checkpointer_context = None
_setup_done = False
_graph_init_lock = None


def _postgres_checkpoint_url(database_url: str) -> str:
    """Convert a SQLAlchemy asyncpg URL into a psycopg connection URL."""
    prefix = "postgresql+asyncpg://"
    if database_url.startswith(prefix):
        return f"postgresql://{database_url[len(prefix):]}"
    return database_url


async def get_supervisor_graph() -> StateGraph:
    """获取编译后的 Supervisor graph（异步初始化 checkpointer）

    由 SUPERVISOR_CHECKPOINTER 控制状态存储后端（与业务数据库 DATABASE_ENABLED 解耦）：
      postgres → AsyncPostgresSaver (PostgreSQL, 默认, 2GB 下较重)
      sqlite   → AsyncSqliteSaver  (落盘, 轻量 + 抗重启, 推荐用于 2GB)
      memory   → MemorySaver       (纯内存, 最轻, 重启即清空)
    PG/SQLite 初始化失败时：生产环境 postgres 失败终止启动，其余降级 MemorySaver。
    """
    global _supervisor_graph, _checkpointer, _checkpointer_context
    global _setup_done, _graph_init_lock

    if _supervisor_graph is not None:
        return _supervisor_graph

    if _graph_init_lock is None:
        _graph_init_lock = asyncio.Lock()

    async with _graph_init_lock:
        if _supervisor_graph is not None:
            return _supervisor_graph

        from app.config import get_settings
        settings = get_settings()

        mode = (settings.supervisor_checkpointer or "postgres").strip().lower()
        context = None
        context_entered = False

        if mode == "postgres" and settings.database_enabled:
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                context = AsyncPostgresSaver.from_conn_string(
                    _postgres_checkpoint_url(settings.database_url)
                )
                _checkpointer = await context.__aenter__()
                context_entered = True
                if not _setup_done:
                    await _checkpointer.setup()
                    _setup_done = True
                _checkpointer_context = context
                logger.info("Checkpointer: AsyncPostgresSaver connected to PostgreSQL")
            except Exception as exc:
                if context is not None and context_entered:
                    await context.__aexit__(type(exc), exc, exc.__traceback__)
                _checkpointer = None
                if settings.app_env.lower() == "production":
                    raise RuntimeError("PostgreSQL checkpointer initialization failed") from exc
                logger.exception(
                    "Failed to initialize PostgreSQL checkpointer; "
                    "using in-memory development fallback"
                )
                _checkpointer = MemorySaver()
        elif mode == "sqlite":
            try:
                import os
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
                db_path = os.environ.get(
                    "SUPERVISOR_CHECKPOINT_DB",
                    "/app/data/checkpoints/supervisor.db",
                )
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                context = AsyncSqliteSaver.from_conn_string(db_path)
                _checkpointer = await context.__aenter__()
                context_entered = True
                if not _setup_done:
                    await _checkpointer.setup()
                    _setup_done = True
                _checkpointer_context = context
                logger.info("Checkpointer: AsyncSqliteSaver at %s", db_path)
            except Exception as exc:
                if context is not None and context_entered:
                    await context.__aexit__(type(exc), exc, exc.__traceback__)
                _checkpointer = None
                logger.exception(
                    "Failed to initialize SQLite checkpointer; "
                    "falling back to in-memory"
                )
                _checkpointer = MemorySaver()
        else:
            # memory mode, or postgres requested without database_enabled
            _checkpointer = MemorySaver()
            logger.info(
                "Checkpointer: MemorySaver (in-memory; mode=%s, database_enabled=%s)",
                mode, settings.database_enabled,
            )

        try:
            workflow = _build_workflow()
            _supervisor_graph = workflow.compile(checkpointer=_checkpointer)
        except Exception as exc:
            if _checkpointer_context is not None:
                await _checkpointer_context.__aexit__(type(exc), exc, exc.__traceback__)
                _checkpointer_context = None
            _checkpointer = None
            raise

        return _supervisor_graph


async def close_supervisor_graph():
    """Release the PostgreSQL checkpointer and reset graph singletons."""
    global _supervisor_graph, _checkpointer, _checkpointer_context
    global _setup_done, _graph_init_lock

    try:
        if _checkpointer_context is not None:
            await _checkpointer_context.__aexit__(None, None, None)
    finally:
        _supervisor_graph = None
        _checkpointer = None
        _checkpointer_context = None
        _setup_done = False
        _graph_init_lock = None
