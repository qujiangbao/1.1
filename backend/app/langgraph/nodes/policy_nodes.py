"""Policy RAG Agent LangGraph Nodes"""
import logging
import re
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from app.tools.gateway import get_tool_gateway

logger = logging.getLogger(__name__)
tg = get_tool_gateway()


_GENERIC_MATCH_TERMS = {
    "广州", "广州市", "企业", "产业", "政策", "申报", "扶持", "产业扶持",
}

_DOMAIN_MATCH_TERMS = (
    "机器人", "人工智能", "智能制造", "新能源", "新材料", "集成电路",
    "生物医药", "数字化", "科技", "专精特新", "中小企业", "补贴",
    "核心零部件", "系统集成", "工业软件", "中试", "人才",
)


def _matched_terms(query: str, *policy_text: object) -> list[str]:
    terms = [
        item.strip().lower()
        for item in re.split(r"[\s,，。；;、/]+", query)
        if len(item.strip()) >= 2
    ]
    query_lower = query.lower()
    terms.extend(term for term in _DOMAIN_MATCH_TERMS if term in query_lower)
    terms = list(dict.fromkeys(terms))
    searchable = " ".join(str(item or "") for item in policy_text).lower()
    matched = list(dict.fromkeys(term for term in terms if term in searchable))
    specific = [term for term in matched if term not in _GENERIC_MATCH_TERMS]
    return (specific or matched)[:6]


class PolicyState(TypedDict):
    task_id: str
    intent: str
    input: Dict[str, Any]
    query: str
    enterprise_id: Optional[str]
    enterprise_profile: Optional[Dict]
    raw_chunks: Optional[List[Dict]]
    filtered_chunks: Optional[List[Dict]]
    search_mode: Optional[str]
    matched_policies: Optional[List[Dict]]
    report: Optional[Dict]
    status: str
    error: Optional[Dict]
    tools_used: List[str]
    data_sources: List[str]


def query_analyzer_node(state: PolicyState) -> PolicyState:
    inp = state.get("input", {})
    state["query"] = inp.get("query", "")
    state["enterprise_id"] = inp.get("enterprise_id")
    state["tools_used"] = []
    state["data_sources"] = []
    state["status"] = "loading" if state["enterprise_id"] else "searching"
    return state


def enterprise_loader_node(state: PolicyState) -> PolicyState:
    if not state.get("enterprise_id"):
        state["status"] = "searching"
        return state
    r = tg.invoke("PolicyAgent", "enterprise_profile_get", {"enterprise_id": state["enterprise_id"]})
    state["enterprise_profile"] = r.data or {}
    state["tools_used"].append("enterprise_profile_get")
    state["data_sources"].append("enterprise_profile")
    state["status"] = "searching"
    return state


def vector_search_node(state: PolicyState) -> PolicyState:
    """向量/混合检索 — P1: 通过 KnowledgeTool (MockAdapter 或 pgvector)"""
    q = state["query"]
    filters = {}

    if state.get("enterprise_profile"):
        ind = state["enterprise_profile"].get("industry", "")
        loc = state["enterprise_profile"].get("location", "")
        if ind:
            q = f"{ind} {q}" if ind else q
            filters["industry"] = ind
        if loc:
            filters["region"] = loc

    # P1: 使用 policy_hybrid_search (KnowledgeTool → PolicyRetriever)
    r = tg.invoke("PolicyAgent", "policy_hybrid_search", {
        "query": q, "top_k": 10, "filters": filters,
    })
    state["raw_chunks"] = r.data.get("chunks", []) if r.status == "success" else []
    state["search_mode"] = r.data.get("mode", "mock") if r.status == "success" else "mock"
    state["tools_used"].append("policy_hybrid_search")
    state["data_sources"].append(f"policy_rag_{state['search_mode']}")
    state["status"] = "filtering"
    return state


def metadata_filter_node(state: PolicyState) -> PolicyState:
    """P1: 内存过滤 — hybrid_search 结果已包含过滤，只需排序去重"""
    chunks = state.get("raw_chunks", [])
    chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
    state["filtered_chunks"] = chunks[:10]
    state["status"] = "matching"
    return state


def policy_matcher_node(state: PolicyState) -> PolicyState:
    chunks = state.get("filtered_chunks", [])
    matched = []
    for c in chunks:
        metadata = c.get("metadata", {})
        evidence = c.get("evidence", [])
        source_url = metadata.get("source_url", "")
        if not source_url and evidence:
            source_url = evidence[0].get("url", "")
        matched_terms = metadata.get("matched_terms") or _matched_terms(
            state.get("query", ""),
            metadata.get("title", c.get("title", "")),
            c.get("content", ""),
        )
        matched.append({
            "policy_id": c.get("policy_id", ""),
            "title": metadata.get("title", c.get("title", "")),
            "content_snippet": str(c.get("content", ""))[:200],
            "level": metadata.get("level", c.get("level", "")),
            "department": metadata.get("department", ""),
            "document_number": metadata.get("document_number", ""),
            "effective_date": metadata.get("effective_date", ""),
            "expire_date": metadata.get("expire_date", ""),
            "status": metadata.get("status", ""),
            "source_url": source_url,
            "source_type": metadata.get("source_type", "public_policy"),
            "source_title": metadata.get("source_title", ""),
            "match_score": round(c.get("score", 0.7) * 100),
            "matched_terms": matched_terms,
            "requirements": metadata.get(
                "requirements",
                c.get("requirements", []),
            ),
        })
    state["matched_policies"] = matched
    state["status"] = "formatting"
    return state


def response_formatter_node(state: PolicyState) -> PolicyState:
    returned_count = len(state.get("matched_policies", []))
    state["report"] = {
        "query": state["query"],
        "total_matched": returned_count,
        "returned_count": returned_count,
        "retrieval_limit": 10,
        "is_exhaustive": False,
        "scope_note": "按当前查询相关度返回前 10 条候选政策，不代表完整政策清单",
        "policies": state.get("matched_policies", []),
        "search_mode": state.get("search_mode", "unknown"),
        "data_sources": state.get("data_sources", []),
    }
    state["status"] = "done"
    return state


def build_policy_graph():
    workflow = StateGraph(PolicyState)
    nodes = [
        ("query_analyzer", query_analyzer_node),
        ("enterprise_loader", enterprise_loader_node),
        ("vector_search", vector_search_node),
        ("metadata_filter", metadata_filter_node),
        ("policy_matcher", policy_matcher_node),
        ("response_formatter", response_formatter_node),
    ]
    for name, node in nodes:
        workflow.add_node(name, node)
    workflow.set_entry_point("query_analyzer")
    for source, target in zip(nodes, nodes[1:]):
        workflow.add_edge(source[0], target[0])
    workflow.add_edge("response_formatter", END)
    return workflow.compile()


_policy_graph = None


def get_policy_graph():
    global _policy_graph
    if _policy_graph is None:
        _policy_graph = build_policy_graph()
    return _policy_graph
