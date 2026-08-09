"""Investment Agent LangGraph Nodes — 7 节点 Pipeline"""
import logging
from app.langgraph.nodes.investment_state import InvestmentState
from app.tools.gateway import get_tool_gateway

logger = logging.getLogger(__name__)
tg = get_tool_gateway()


def intent_parser_node(state: InvestmentState) -> InvestmentState:
    input_data = state.get("input", {})
    state["query"] = input_data.get("query", "")
    state["industry"] = input_data.get("industry", "")
    state["region"] = input_data.get("region", "guangzhou")
    state["status"] = "searching"
    state["tools_used"] = []
    state["data_sources"] = []
    state["retry_count"] = 0
    logger.info(f"[Investment] Parsing intent: {state['query'][:50]}")
    return state


def enterprise_search_node(state: InvestmentState) -> InvestmentState:
    result = tg.invoke("InvestmentAgent", "enterprise_search", {
        "keyword": state["query"],
        "industry": state["industry"],
        "region": state["region"],
        "limit": 20,
    })
    if result.status == "success":
        state["search_results"] = result.data.get("enterprises", [])
        state["enterprise_ids"] = [e.get("id", e.get("enterprise_id", f"E{i:03d}"))
                                   for i, e in enumerate(state["search_results"])]
        state["tools_used"].append("enterprise_search")
        state["data_sources"].append("enterprise")
        state["status"] = "profiling" if state["search_results"] else "done"
    else:
        state["error"] = {"code": "SEARCH_FAILED", "message": result.error}
        state["status"] = "failed"
    return state


def enterprise_profile_node(state: InvestmentState) -> InvestmentState:
    profiles = []
    for eid in state.get("enterprise_ids", [])[:10]:
        result = tg.invoke("InvestmentAgent", "enterprise_profile_get", {"enterprise_id": eid})
        if result.status == "success":
            profiles.append(result.data or {})
    state["profiles"] = profiles
    state["tools_used"].append("enterprise_profile_get")
    state["data_sources"].append("enterprise_profile")
    state["status"] = "scoring"
    return state


def scoring_node(state: InvestmentState) -> InvestmentState:
    """Investment Score = 产业匹配×30% + 成长×25% + 技术×20% + 资本×15% + 人才×10%"""
    scores = []
    for p in state.get("profiles", []):
        result = tg.invoke("InvestmentAgent", "investment_scoring", {"enterprise_id": p.get("enterprise_id", "")})
        score_data = result.data or {}
        score = score_data.get("score")
        scores.append({
            "enterprise_id": p.get("enterprise_id"),
            "name": p.get("name", ""),
            "industry": p.get("industry", ""),
            "location": p.get("location", ""),
            "registered_capital": p.get("registered_capital", ""),
            "match_reason": p.get("match_reason", ""),
            "score": score,
            "level": _score_level(score),
            "match_reasons": score_data.get("reasons", []),
        })
    scores.sort(
        key=lambda item: (
            item["score"] is not None,
            item["score"] if item["score"] is not None else 0,
        ),
        reverse=True,
    )
    state["scores"] = scores
    state["tools_used"].append("investment_scoring")
    state["status"] = "recommending"
    return state


def _score_level(score: float | None) -> str:
    if score is None: return "DATA_INSUFFICIENT"
    if score >= 85: return "STRONG_RECOMMEND"
    if score >= 70: return "RECOMMEND"
    if score >= 50: return "CONSIDER"
    return "LOW_PRIORITY"


def recommendation_node(state: InvestmentState) -> InvestmentState:
    recs = []
    for s in state.get("scores", []):
        score = s["score"]
        recs.append({
            **s,
            "action": (
                "待补充经营与知识产权数据"
                if score is None
                else {85: "优先接触", 70: "积极跟进", 50: "保持关注"}.get(
                    next((t for t in [85, 70, 50] if score >= t), 0), "暂不跟进"
                )
            ),
        })
    state["recommendations"] = recs
    state["status"] = "generating_strategy"
    return state


def strategy_generator_node(state: InvestmentState) -> InvestmentState:
    top = [
        item for item in state.get("recommendations", [])
        if item.get("level") in ("STRONG_RECOMMEND", "RECOMMEND")
    ][:5]
    state["strategy"] = {
        "summary": (
            f"基于现有可验证评分，推荐 {len(top)} 家企业进入人工复核。"
            if top
            else "已检索公开企业快照，但评分字段不足，未生成自动推荐名单。"
        ),
        "targets": [{"name": t["name"], "score": t["score"], "action": t["action"]} for t in top],
    }
    state["status"] = "generating_report"
    return state


def report_generator_node(state: InvestmentState) -> InvestmentState:
    state["report"] = {
        "task_id": state["task_id"],
        "summary": {
            "total_found": len(state.get("search_results", [])),
            "recommended": len([r for r in state.get("recommendations", [])
                               if r["level"] in ("STRONG_RECOMMEND", "RECOMMEND")]),
        },
        "enterprises": state.get("recommendations", []),
        "strategy": state.get("strategy", {}),
    }
    state["status"] = "done"
    return state
