"""Supervisor LangGraph Nodes — LLM Gateway 驱动版本"""
import logging
from uuid import uuid4
from datetime import datetime, timezone

from app.langgraph.state import SupervisorState, TaskNode, TraceStep, AgentResult
from app.agents.registry import AGENT_REGISTRY
from app.core.llm_gateway import get_llm_gateway
from app.agents.executor import execute_business_agent
from app.services.runtime_metrics import get_runtime_metrics

logger = logging.getLogger(__name__)

# P3: EventBus 事件发布辅助
def _emit_event(state: SupervisorState, event_type: str, payload: dict,
                 source: str = "supervisor") -> None:
    """发布事件到 EventBus (非阻塞)"""
    import asyncio
    from app.services.event_bus import get_event_bus
    task_id = state.get("trace_id", "")
    if not task_id:
        return
    event_bus = get_event_bus()
    asyncio.ensure_future(event_bus.publish(task_id, event_type, payload, source=source))


def _wrap_node(node_name: str):
    """节点包装器: 在每个 supervisor node 前后发布事件 (不修改节点逻辑)"""
    def decorator(fn):
        def wrapper(state: SupervisorState) -> SupervisorState:
            _emit_event(state, "supervisor_node", {"node": node_name, "phase": "start"})
            try:
                result = fn(state)
                _emit_event(result, "supervisor_node",
                            {"node": node_name, "phase": "complete"})
                return result
            except Exception as e:
                _emit_event(state, "supervisor_node",
                            {"node": node_name, "phase": "error", "error": str(e)})
                raise
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator


def _wrap_agent_router(fn):
    """Agent 路由包装器: 在 agent 执行前后发布事件 (不修改原有逻辑)"""
    def wrapper(state: SupervisorState) -> SupervisorState:
        # 记录执行前的 task 状态
        task_plan = state.get("task_plan", [])
        idx = state.get("current_task_index", 0)
        if 0 <= idx < len(task_plan):
            task = task_plan[idx]
            if task.get("status") not in ("completed", "failed"):
                agent = task["agent"]
                display = AGENT_REGISTRY.get(agent, {}).get("display", agent)
                _emit_event(state, "agent_start", {
                    "agent": agent, "display": display,
                    "task_id": task.get("task_id", ""),
                    "intent": task.get("intent", ""),
                }, source="supervisor")

        # 执行原有逻辑
        try:
            result = fn(state)
        except Exception:
            # 发布 agent_error
            if 0 <= idx < len(task_plan):
                task = task_plan[idx]
                _emit_event(state, "agent_error", {
                    "agent": task.get("agent", ""),
                    "task_id": task.get("task_id", ""),
                }, source="supervisor")
            raise

        # 执行后发布 agent_done
        task_plan_after = result.get("task_plan", [])
        agent_results = result.get("agent_results", {})
        for agent, ar in agent_results.items():
            summary = (ar.get("result") or {}).get("summary", "")
            _emit_event(result, "agent_complete", {
                "agent": agent,
                "status": ar.get("status", "unknown"),
                "summary": summary[:200],
                "execution_time_ms": ar.get("execution_time_ms", 0),
            }, source="supervisor")

        return result

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper

# Intent → Agent 路由表
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

KEYWORD_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "industry_analysis",
        (
            "产业", "产业链", "行业分析", "行业趋势", "市场规模", "市场趋势",
            "市场分析", "竞争格局", "上游", "中游", "下游", "集群", "赛道",
        ),
    ),
    (
        "investment_search",
        (
            "招商", "寻商", "引进企业", "目标企业", "候选企业", "企业画像",
            "企业评分", "落地意愿", "投资推荐", "投资机会", "选址",
        ),
    ),
    (
        "risk_single",
        (
            "风险", "预警", "合规", "诉讼", "失信", "处罚", "经营异常",
            "舆情", "客户集中", "供应链风险", "现金流",
        ),
    ),
    (
        "policy_match",
        (
            "政策", "补贴", "申报", "扶持", "奖励", "资助", "税收优惠",
            "惠企", "申报资格", "申报条件",
        ),
    ),
    (
        "dashboard_kpi",
        (
            "经营指标", "运营指标", "招商漏斗", "经营分析", "经营看板",
            "驾驶舱", "kpi", "报表", "统计汇总", "数据汇总", "趋势图",
        ),
    ),
    (
        "service_request",
        (
            "企业服务", "服务工单", "工单", "诉求", "报修", "投诉", "物业",
            "空调", "水电", "停车", "会议室", "搬迁", "临时增容", "入驻手续",
            "场地服务", "人才招聘",
        ),
    ),
)


def _add_trace(state: SupervisorState, type_: str, agent: str, action: str,
               input_: dict, output_: dict, duration_ms: int):
    step: TraceStep = {
        "step": len(state.get("trace_steps", [])) + 1,
        "type": type_,
        "agent": agent,
        "action": action,
        "input": input_,
        "output": output_,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
    }
    if "trace_steps" not in state:
        state["trace_steps"] = []
    state["trace_steps"].append(step)


# ==================== Node 1: User Input ====================
def user_input_node(state: SupervisorState) -> SupervisorState:
    state["status"] = "running"
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["trace_id"] = str(uuid4())
    state["agent_results"] = {}
    state["trace_steps"] = []
    state["error_count"] = 0
    state["retry_count"] = 0

    # P2: 注入对话历史（API 层通过 history_messages 传入）
    history = state.get("history_messages", [])
    if history:
        existing = state.get("messages", [])
        state["messages"] = history + existing

    # P2: 保存用户消息到 messages 用于 checkpointer 持久化
    if "messages" not in state or not state["messages"]:
        state["messages"] = []
    state["messages"] = state.get("messages", []) + [{
        "role": "user",
        "content": state.get("user_query", ""),
        "timestamp": state["started_at"],
    }]
    return state


# ==================== Node 2: Intent Recognition ====================
def intent_recognition_node(state: SupervisorState) -> SupervisorState:
    query = state["user_query"]
    llm = get_llm_gateway()

    prompt = f"""你是产业园AI运营官的意图识别器。分析用户输入并返回JSON。

可用意图: {list(INTENT_ROUTING.keys())}
如果涉及多个Agent协作(如"找企业并评估风险")，is_compound为true。

用户输入: {query}

只返回JSON: {{"intent":"主意图","intents":["意图列表"],"entities":{{}},"is_compound":false,"confidence":0.0}}"""

    try:
        result = llm.invoke_sync("Supervisor", "simple", prompt, max_tokens=200, temperature=0)
        import json
        parsed = json.loads(result.content)
    except Exception as e:
        logger.warning(f"LLM intent recognition failed: {e}, using keyword fallback")
        parsed = _keyword_intent_fallback(query)

    raw_intents = parsed.get("intents") or [parsed.get("intent")]
    if isinstance(raw_intents, str):
        raw_intents = [raw_intents]
    valid_intents = list(dict.fromkeys(
        intent for intent in raw_intents if intent in INTENT_ROUTING
    ))
    if not valid_intents:
        parsed = _keyword_intent_fallback(query)
        valid_intents = parsed["intents"]

    state["intent"] = valid_intents[0] if valid_intents else "general_query"
    state["intents"] = valid_intents
    state["entities"] = parsed.get("entities", {})
    state["confidence"] = parsed.get("confidence", 0.8)

    _add_trace(state, "supervisor_decision", "Supervisor", "intent_recognition",
               {"query": query[:100]}, {"intent": state["intent"]}, 500)
    return state


def _keyword_intent_fallback(query: str) -> dict:
    """LLM 失败时的关键词兜底"""
    q = query.lower()
    intents = [
        intent
        for intent, keywords in KEYWORD_INTENT_RULES
        if any(keyword in q for keyword in keywords)
    ]
    return {
        "intent": intents[0] if intents else "general_query",
        "intents": intents,
        "entities": {},
        "is_compound": len(intents) > 1,
        "confidence": 0.6 if intents else 0.2,
    }


# ==================== Node 3: Task Planner ====================
def task_planner_node(state: SupervisorState) -> SupervisorState:
    intents = state.get("intents", [])
    user_role = str(state.get("user_role", "park_manager"))
    task_plan: list[TaskNode] = []

    # P4: ROLE_AGENT_WHITELIST — 角色过滤可调用的 Agent
    from app.core.permissions import ROLE_AGENT_WHITELIST
    allowed_agents = ROLE_AGENT_WHITELIST.get(user_role, ["*"])

    for i, intent in enumerate(intents):
        agent = INTENT_ROUTING.get(intent)
        if not agent:
            continue
        # P4: 跳过无权限的 Agent
        if "*" not in allowed_agents and agent not in allowed_agents:
            logger.info("[P4] Task planner: skipping %s (role=%s not permitted)", agent, user_role)
            continue
        task: TaskNode = {
            "task_id": f"{state['trace_id']}-{i}",
            "agent": agent,
            "intent": intent,
            "input": {
                "query": state["user_query"],
                "intent": intent,
                "data_mode": state.get("data_mode", "real"),
                "current_date": state.get("current_date", ""),
                "data_context": state.get("data_context", {}),
                **state.get("entities", {}),
            },
            "expected_output": AGENT_REGISTRY.get(agent, {}).get("capabilities", [])[:3],
            "dependencies": [],
            "priority": "high" if i == 0 else "medium",
            "status": "pending",
        }
        task_plan.append(task)

    state["task_plan"] = task_plan
    state["current_task_index"] = 0
    _add_trace(state, "supervisor_decision", "Supervisor", "task_planning",
               {"intents": intents}, {"tasks": [t["agent"] for t in task_plan]}, 5)
    return state


# ==================== Node 4: Agent Router ====================
def agent_router_node(state: SupervisorState) -> SupervisorState:
    task_plan = state.get("task_plan", [])
    idx = state.get("current_task_index", 0)

    if idx >= len(task_plan):
        return state

    task = task_plan[idx]

    # P2: 跳过 completed 和 failed 的 task（断点续跑）
    if task.get("status") in ("completed", "failed"):
        state["current_task_index"] = idx + 1
        return state

    task["status"] = "running"
    agent = task["agent"]
    display = AGENT_REGISTRY.get(agent, {}).get("display", agent)
    runtime_metrics = get_runtime_metrics()
    metric_started = runtime_metrics.begin(agent, task["task_id"])

    try:
        result: AgentResult = execute_business_agent(agent, task, state)
    except Exception as exc:
        logger.exception("%s execution failed", agent)
        result = {
            "task_id": task["task_id"], "agent": agent, "status": "failed",
            "result": None,
            "error": {"code": "AGENT_EXECUTION_FAILED", "message": str(exc)},
            "trace": {"tools_used": [], "data_sources": []},
            "execution_time_ms": 0,
        }
    runtime_metrics.finish(
        agent,
        task["task_id"],
        result["status"],
        metric_started,
        result.get("execution_time_ms", 0),
    )

    state["agent_results"][agent] = result
    task["status"] = "completed" if result["status"] == "success" else "failed"
    state["current_task_index"] = idx + 1

    _add_trace(state, "agent_call", agent, task["intent"],
               task.get("input", {}), result.get("result") or result.get("error", {}),
               result.get("execution_time_ms", 0))
    return state


# ==================== Node 5: Result Validator ====================
def result_validator_node(state: SupervisorState) -> SupervisorState:
    for agent, result in state.get("agent_results", {}).items():
        if result.get("status") == "failed":
            state["status"] = "failed"
            return state
    return state


# ==================== Node 6: Result Aggregator ====================
def result_aggregator_node(state: SupervisorState) -> SupervisorState:
    results = state.get("agent_results", {})
    data_mode = state.get("data_mode", "real")
    current_date = state.get("current_date", "")
    mode_notice = (
        f"> **演示沙盘 · 非真实经营数据** | 生成日期：{current_date}"
        if data_mode == "demo"
        else f"> **公开数据快照** | 生成日期：{current_date} | 无证据字段标记为“待接入/尚未评估”"
    )
    if not results:
        state["aggregated_result"] = ""
        state["final_response"] = (
            f"{mode_notice}\n\n# 暂未识别到可执行任务\n\n"
            "请明确说明需要产业分析、招商寻商、风险核验、政策匹配、"
            "经营指标查询或企业服务咨询中的哪一类事项。"
        )
        return state

    parts = []
    for agent, result in results.items():
        display = AGENT_REGISTRY.get(agent, {}).get("display", agent)
        payload = result.get("result") or {}
        error = result.get("error") or {}
        summary = payload.get("summary") or f"执行失败：{error.get('message', '未知错误')}"
        parts.append(f"## {display}\n{summary}")

    state["aggregated_result"] = "\n\n".join(parts)

    # A single PolicyAgent result is already structured and traceable. Avoid a
    # second external LLM call that can delay or paraphrase away citations.
    if len(results) == 1 and "PolicyAgent" in results:
        policy_summary = (
            results["PolicyAgent"].get("result", {}).get("summary", "")
        )
        state["final_response"] = (
            f"{mode_notice}\n\n# 政策匹配结果\n\n{policy_summary}"
        )
    else:
        # 使用 LLM 生成多 Agent 自然语言报告
        try:
            llm = get_llm_gateway()
            prompt = f"""你是产业园AI运营总经理。根据以下 Agent 执行结果，用中文生成面向用户的综合报告。

当前日期：{current_date}
当前数据模式：{"演示沙盘（固定合成场景）" if data_mode == "demo" else "公开数据快照"}

硬性规则：
1. 只能使用下方 Agent 结果中明确出现的数字、企业名称、风险等级和结论。
2. 禁止补写、推测或美化任何评分、企业数量、融资、扩产、签约和市场规模。
3. 证据不足时必须写“待接入”“尚未评估”或“证据不足”，不能写 0 分、UNKNOWN 后继续下结论。
4. 日期必须使用 {current_date}，不得生成其他报告日期。
5. 演示模式中的指标必须称为“演示数据/示例企业”；公开快照模式不得把演示数据写成真实数据。
6. 末尾用一行说明“数据口径与可信度”。

Agent 执行结果：

{state['aggregated_result']}"""
            resp = llm.invoke_sync("Supervisor", "simple", prompt, max_tokens=500, temperature=0.3)
            state["final_response"] = f"{mode_notice}\n\n{resp.content}"
        except Exception as e:
            logger.warning(f"LLM aggregation failed: {e}")
            state["final_response"] = (
                f"{mode_notice}\n\n# 处理结果\n\n{state['aggregated_result']}"
                f"\n\n---\n*Trace ID: {state.get('trace_id', '')}*"
            )

    # The natural-language aggregation step must not drop authoritative policy
    # citations. Always provide a deterministic source appendix.
    policy_data = (
        results.get("PolicyAgent", {})
        .get("result", {})
        .get("data", {})
    )
    missing_sources = []
    seen_urls = set()
    policy_candidates = policy_data.get("policies", [])
    for policy in policy_candidates[:3]:
        source_url = str(policy.get("source_url", "")).strip()
        if (
            not source_url
            or source_url in seen_urls
        ):
            continue
        seen_urls.add(source_url)
        title = " ".join(str(policy.get("title", "")).split()) or "政策原文"
        missing_sources.append(f"- {title}：{source_url}")
    if missing_sources:
        state["final_response"] += (
            "\n\n## 政策来源\n" + "\n".join(missing_sources)
        )
        if len(policy_candidates) > 3:
            state["final_response"] += (
                f"\n\n其余 {len(policy_candidates) - 3} 条候选政策不在工作台展开；"
                "请进入“惠企政策库”查看完整政策库并重新筛选。"
            )

    _add_trace(state, "supervisor_decision", "Supervisor", "result_aggregation",
               {"agent_count": len(results)}, {"response_length": len(state["final_response"])}, 5)
    return state


# ==================== Node 7: Final Response ====================
def final_response_node(state: SupervisorState) -> SupervisorState:
    state["status"] = "completed"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()

    # P2: 追加 assistant 消息到 messages（checkpointer 自动持久化）
    messages = list(state.get("messages", []))
    messages.append({
        "role": "assistant",
        "content": state.get("final_response", ""),
        "timestamp": state["completed_at"],
    })
    state["messages"] = messages
    return state
