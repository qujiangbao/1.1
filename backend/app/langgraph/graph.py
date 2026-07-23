"""Supervisor LangGraph — 核心编排图"""
import time
import logging
from uuid import uuid4
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.langgraph.state import SupervisorState, TaskNode, TraceStep
from app.agents.registry import find_agent_by_capability, AGENT_REGISTRY

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
    # MVP 阶段不启用审批
    return "finalize_response"


def build_supervisor_graph() -> StateGraph:
    from app.langgraph.nodes.supervisor_nodes import (
        user_input_node, intent_recognition_node, task_planner_node,
        agent_router_node, result_validator_node, result_aggregator_node, final_response_node,
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

    # 标准流程
    workflow.add_edge("user_input", "intent_recognition")
    workflow.add_edge("intent_recognition", "task_planner")
    workflow.add_edge("task_planner", "agent_router")

    # 条件：Agent 执行后去哪
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

    return workflow.compile(checkpointer=MemorySaver())


# 全局单例
_supervisor_graph = None


def get_supervisor_graph() -> StateGraph:
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = build_supervisor_graph()
    return _supervisor_graph
