"""Business-agent dispatcher used by the Supervisor graph.

All business data access remains inside each agent through ToolGateway.  This
module only selects and invokes the appropriate compiled business graph.
"""
from __future__ import annotations

import re
import time
from typing import Any


def _enterprise_id(task_input: dict[str, Any], supervisor_state: dict[str, Any]) -> str:
    explicit = task_input.get("enterprise_id")
    if explicit:
        return str(explicit)

    match = re.search(r"\b(?:ENT-|E)\d+\b", str(task_input.get("query", "")), re.I)
    if match:
        return match.group(0).upper()

    investment = supervisor_state.get("agent_results", {}).get("InvestmentAgent", {})
    enterprises = investment.get("result", {}).get("data", {}).get("enterprises", [])
    if enterprises:
        return str(enterprises[0].get("enterprise_id", "ENT-001"))
    return "ENT-001"


def _summary(agent_name: str, result: dict[str, Any]) -> str:
    if agent_name == "IndustryAgent":
        chain = result.get("chain", {})
        gaps = "、".join(g.get("name", "") for g in chain.get("gaps", [])) or "暂无明显缺口"
        return f"产业趋势评分 {result.get('trend_score', 0)}，重点缺口：{gaps}。"
    if agent_name == "InvestmentAgent":
        summary = result.get("summary", {})
        enterprises = result.get("enterprises", [])
        names = "、".join(e.get("name", "") for e in enterprises[:5])
        return f"发现 {summary.get('total_found', 0)} 家目标企业，推荐 {summary.get('recommended', 0)} 家：{names}。"
    if agent_name == "RiskAgent":
        return f"{result.get('enterprise_name') or result.get('enterprise_id')} 风险评分 {result.get('risk_score', 0)}，等级 {result.get('risk_level', 'UNKNOWN')}。"
    if agent_name == "PolicyAgent":
        policies = result.get("policies", [])
        titles = "、".join(p.get("title", "") for p in policies[:3])
        return f"匹配 {result.get('total_matched', 0)} 条政策：{titles}。"
    if agent_name == "EnterpriseServiceAgent":
        return f"企业服务工单 {result.get('ticket_id', '')} 已生成。"
    if agent_name == "BIAgent":
        return result.get("insight", {}).get("summary", "驾驶舱指标已汇总。")
    return "任务已完成。"


def execute_business_agent(agent_name: str, task: dict[str, Any], supervisor_state: dict[str, Any]) -> dict[str, Any]:
    """Execute one registered business agent and normalize its result."""
    started = time.perf_counter()
    task_input = dict(task.get("input", {}))
    task_id = task["task_id"]

    if agent_name == "InvestmentAgent":
        from app.langgraph.graphs.investment_graph import get_investment_graph

        raw = get_investment_graph().invoke({
            "task_id": task_id,
            "intent": task["intent"],
            "priority": task.get("priority", "medium"),
            "input": task_input,
            "status": "idle",
            "tools_used": [],
            "data_sources": [],
        })
        data = raw.get("report", {})
    elif agent_name == "IndustryAgent":
        from app.langgraph.nodes.industry_nodes import get_industry_graph

        raw = get_industry_graph().invoke({
            "task_id": task_id, "intent": task["intent"], "input": task_input,
            "status": "idle", "tools_used": [], "data_sources": [],
        })
        data = raw.get("report", {})
    elif agent_name == "RiskAgent":
        from app.langgraph.nodes.risk_nodes import get_risk_graph

        task_input["enterprise_id"] = _enterprise_id(task_input, supervisor_state)
        raw = get_risk_graph().invoke({
            "task_id": task_id, "intent": task["intent"], "input": task_input,
            "status": "idle", "tools_used": [], "data_sources": [],
        })
        if raw.get("status") == "failed":
            raise ValueError(raw.get("error", {}).get("message", "风险分析失败"))
        data = raw.get("report", {})
    elif agent_name == "PolicyAgent":
        from app.langgraph.nodes.policy_nodes import get_policy_graph

        raw = get_policy_graph().invoke({
            "task_id": task_id, "intent": task["intent"], "input": task_input,
            "status": "idle", "tools_used": [], "data_sources": [],
        })
        data = raw.get("report", {})
    elif agent_name == "EnterpriseServiceAgent":
        from app.langgraph.nodes.service_nodes import get_service_graph

        task_input.setdefault("request", task_input.get("query", ""))
        raw = get_service_graph().invoke({
            "task_id": task_id, "input": task_input, "status": "idle", "tools_used": [],
        })
        data = raw.get("final_response", {})
    elif agent_name == "BIAgent":
        from app.langgraph.nodes.bi_nodes import get_bi_graph

        raw = get_bi_graph().invoke({
            "task_id": task_id, "intent": task["intent"],
            "input": {**task_input, "dashboard_type": "overview"}, "status": "idle",
        })
        data = {
            "kpi": raw.get("kpi_result", {}),
            "dashboard": raw.get("dashboard_result", {}),
            "insight": raw.get("insight_result", {}),
        }
    else:
        raise ValueError(f"Unsupported agent: {agent_name}")

    elapsed_ms = max(1, int((time.perf_counter() - started) * 1000))
    return {
        "task_id": task_id,
        "agent": agent_name,
        "status": "success",
        "result": {"summary": _summary(agent_name, data), "data": data},
        "error": None,
        "trace": {
            "tools_used": raw.get("tools_used", []),
            "data_sources": raw.get("data_sources", []),
        },
        "execution_time_ms": elapsed_ms,
    }
