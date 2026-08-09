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
    is_demo = result.get("evidence_level") == "synthetic"

    if agent_name == "IndustryAgent":
        chain = result.get("chain", {})
        score = result.get("trend_score")
        gaps = [g.get("name", "") for g in chain.get("gaps", []) if g.get("name")]
        if score is None:
            total = chain.get("enterprise_total", 0)
            counts = chain.get("layer_counts", {})
            if total:
                return (
                    f"当前公开企业快照检索到 {total} 条相关线索；"
                    f"核心零部件/基础能力 {counts.get('upstream', 0)} 条，"
                    f"本体/平台/系统集成 {counts.get('midstream', 0)} 条，"
                    f"场景应用/服务 {counts.get('downstream', 0)} 条。"
                    f"{'当前快照覆盖缺口：' + '、'.join(gaps) + '。' if gaps else ''}"
                    "尚无权威市场规模与时间序列，因此不生成趋势分数；"
                    "以上仅表示线索库覆盖，不等同于真实产业缺口。"
                )
            return "未检索到可验证的产业企业快照；未生成趋势分数或产业链结论。"
        if is_demo:
            upstream = "、".join(chain.get("upstream", [])[:3])
            midstream = "、".join(chain.get("midstream", [])[:2])
            downstream = "、".join(chain.get("downstream", [])[:2])
            gap_text = "、".join(gaps) if gaps else "暂未识别明显缺口"
            return (
                f"机器人产业链态势：上游 {upstream}，中游 {midstream}，下游 {downstream}。"
                f"产业趋势综合评分 {score} 分，产业链完整度 {chain.get('completeness', '—')}%。"
                f"当前关键缺口：{gap_text}。"
                f"建议优先在高端传感器和控制系统方向布局招商。"
            )
        return (
            f"产业趋势综合评分 {score}，产业链完整度 {chain.get('completeness', '—')}%，"
            f"关键缺口：{'、'.join(gaps) if gaps else '暂未识别明显缺口'}。"
        )
    if agent_name == "InvestmentAgent":
        summary = result.get("summary", {})
        enterprises = result.get("enterprises", [])
        recommended = [
            item for item in enterprises
            if item.get("level") in ("STRONG_RECOMMEND", "RECOMMEND")
        ]
        if not recommended:
            return (
                f"检索到 {summary.get('total_found', 0)} 条公开企业快照候选；"
                "因经营与评分证据不足，未生成自动推荐名单。"
            )
        total = summary.get("total_found", 0)
        rec_count = summary.get("recommended", 0)
        lines = [
            f"在产业分析基础上，从{'演示示例企业库' if is_demo else '公开企业快照'}中匹配到 {total} 家目标企业，"
            f"按产业匹配度、技术能力和成长潜力综合评分后，推荐以下 {rec_count} 家优先接洽：",
            "",
        ]
        level_labels = {"STRONG_RECOMMEND": "强烈推荐", "RECOMMEND": "推荐"}
        for i, e in enumerate(recommended[:5], 1):
            industry = e.get("industry", "")
            score_str = f"{e.get('score', '—')}分"
            level = level_labels.get(e.get("level", ""), e.get("level", ""))
            lines.append(f"{i}. **{e.get('name', '')}**（{industry} · {score_str} · {level}）")
        lines.append("")
        if is_demo:
            lines.append("以上为演示合成数据，用于展示招商决策闭环。如需正式寻商，请在招商决策中心使用公开数据创建场景。")
        else:
            lines.append("建议优先与高评分企业建立初步接触。如需进入正式招商流程，请前往招商决策中心加入候选池并分配负责人。")
        return "\n".join(lines)
    if agent_name == "RiskAgent":
        name = result.get("enterprise_name") or result.get("enterprise_id") or "目标企业"
        score = result.get("risk_score")
        level = result.get("risk_level")
        reason = result.get("risk_reason", "")
        action = result.get("action", "")
        if score is None or not level or level == "UNKNOWN":
            return f"{name} 的风险证据不足，尚未评估；当前不生成风险分数或风险等级，保持 UNKNOWN。"
        level_cn = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}.get(level, level)
        lines = [f"**{name}** 风险评估结果：{level_cn}（{score} 分）"]
        if reason:
            lines.append(f"风险原因：{reason}")
        if action:
            lines.append(f"建议行动：{action}")
        if is_demo:
            lines.append("（演示合成数据，用于展示风险评估流程）")
        return "\n".join(lines)
    if agent_name == "PolicyAgent":
        policies = result.get("policies", [])
        if not policies:
            return "未匹配到相关政策，建议扩大检索范围或调整产业方向。"
        returned_count = result.get("returned_count", result.get("total_matched", len(policies)))
        preview_count = min(3, len(policies))
        lines = [
            f"当前检索返回 {returned_count} 条候选政策，工作台展示相关度最高的前 {preview_count} 条。",
            "这不是完整政策清单；未展示或未召回的政策不等于不适用。",
            "",
        ]
        for i, policy in enumerate(policies[:preview_count], 1):
            title = str(policy.get("title", "")).strip() or "未命名政策"
            source_url = str(policy.get("source_url", "")).strip()
            source_type = str(policy.get("source_type", "")).strip()
            source_title = str(policy.get("source_title", "")).strip()
            match_level = policy.get("match_level", "")
            match_tag = f" [{match_level}]" if match_level else ""
            lines.append(f"{i}. **{title}**{match_tag}")
            match_score = policy.get("match_score")
            matched_terms = [
                str(term) for term in (policy.get("matched_terms") or []) if str(term).strip()
            ]
            if match_score is not None or matched_terms:
                details = []
                if match_score is not None:
                    details.append(f"检索相关度 {float(match_score):.0f}%")
                if matched_terms:
                    details.append(f"命中词：{'、'.join(matched_terms)}")
                lines.append(f"   {'；'.join(details)}")
            if source_type == "park_private_document":
                lines.append(f"   来源：园区上传资料《{source_title or title}》")
            elif source_url:
                lines.append(f"   来源：{source_url}")
        lines.extend([
            "",
            "匹配依据：当前任务的产业方向、产业链环节和所在地，与政策标题、发布信息及正文相关度排序；申报资格仍按结构化条件逐项核验。",
            "完整政策浏览与组合筛选请进入“惠企政策库”。",
        ])
        return "\n".join(lines)
    if agent_name == "EnterpriseServiceAgent":
        service_name = result.get("service_name", "企业服务")
        next_steps = result.get("next_steps", [])
        steps = "；".join(str(item) for item in next_steps if item)
        return (
            f"已识别为{service_name}需求。本次对话不会擅自创建业务工单；"
            f"请在“企业服务工单”提交后进入正式受理流程。建议：{steps or '补充企业名称和具体诉求'}。"
        )
    if agent_name == "BIAgent":
        kpi = result.get("kpi", {})
        insight_summary = result.get("insight", {}).get("summary", "")
        lines = [insight_summary or "经营指标已汇总：", ""]
        if kpi:
            lines.append(f"- 企业总数：{kpi.get('enterprise_total', '—')} 家")
            lines.append(f"- 招商目标池：{kpi.get('investment_targets', '—')} 家")
            lines.append(f"- 高风险企业：{kpi.get('risk_high', '—')} 家")
        return "\n".join(lines)
    return "任务已完成。"


def execute_business_agent(agent_name: str, task: dict[str, Any], supervisor_state: dict[str, Any]) -> dict[str, Any]:
    """Execute one registered business agent and normalize its result."""
    started = time.perf_counter()
    task_input = dict(task.get("input", {}))
    task_id = task["task_id"]
    demo_data = None
    if task_input.get("data_mode") == "demo" and agent_name != "PolicyAgent":
        from app.services.demo_scenario import agent_result

        demo_data = agent_result(agent_name)

    if demo_data is not None:
        data = demo_data
        raw = {
            "tools_used": ["demo_scenario"],
            "data_sources": ["demo_scenario"],
        }

    elif agent_name == "InvestmentAgent":
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
