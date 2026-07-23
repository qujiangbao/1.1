"""Business API routes — Investment, Risk, Policy"""
from fastapi import APIRouter
from app.langgraph.graphs.investment_graph import get_investment_graph
from datetime import date
from uuid import uuid4
import asyncio

router = APIRouter()


# === Investment ===
@router.post("/investment/search")
async def investment_search(request: dict):
    graph = get_investment_graph()
    keyword = request.get("keyword") or request.get("industry") or request.get("query", "")
    state = {
        "task_id": f"inv-{uuid4()}",
        "intent": "investment_search",
        "priority": "high",
        "input": {
            "query": keyword,
            "industry": request.get("industry", keyword),
            "region": request.get("region", "guangzhou"),
        },
        "status": "idle",
        "tools_used": [],
        "data_sources": [],
    }
    result = await asyncio.to_thread(graph.invoke, state)
    return {
        "success": True,
        "data": {
            "enterprises": result.get("recommendations", []),
            "strategy": result.get("strategy", {}),
            "total": len(result.get("search_results", [])),
        },
    }


@router.get("/investment/profile/{enterprise_id}")
async def investment_profile(enterprise_id: str):
    from app.tools.gateway import get_tool_gateway
    tg = get_tool_gateway()
    r = tg.invoke("InvestmentAgent", "enterprise_profile_get", {"enterprise_id": enterprise_id})
    return {"success": True, "data": r.data}


# === Risk ===
@router.post("/risk/analyze")
async def risk_analyze(request: dict):
    eid = request.get("enterprise_id", "")
    from app.tools.gateway import get_tool_gateway
    tg = get_tool_gateway()
    basic = tg.invoke("RiskAgent", "enterprise_query", {"enterprise_id": eid})
    profile = tg.invoke("RiskAgent", "enterprise_profile_get", {"enterprise_id": eid})

    # Simplified scoring
    p = profile.data or {}
    score = 28  # Mock for demo
    level = "LOW" if score <= 30 else ("MEDIUM" if score <= 70 else "HIGH")

    return {
        "success": True,
        "data": {
            "enterprise_id": eid,
            "enterprise_name": (basic.data or {}).get("name", ""),
            "risk_score": score,
            "risk_level": level,
            "risk_factors": [
                {"type": "business", "detail": "经营正常"},
                {"type": "finance", "detail": "融资正常"},
            ],
            "recommendation": "正常关注",
        },
    }


@router.post("/risk/predict")
async def risk_predict(request: dict):
    eid = request.get("enterprise_id", "")
    return {
        "success": True,
        "data": {
            "enterprise_id": eid,
            "current_score": 45,
            "predicted_90d": 52,
            "direction": "stable",
            "warnings": [],
        },
    }


# === Policy ===
@router.post("/policy/search")
async def policy_search(request: dict):
    from app.tools.gateway import get_tool_gateway
    tg = get_tool_gateway()
    r = tg.invoke("PolicyAgent", "policy_vector_search", {
        "query": request.get("query", ""),
        "top_k": 10,
    })
    chunks = r.data.get("chunks", []) if r.status == "success" else []
    return {
        "success": True,
        "data": {
            "policies": [
                {"title": c.get("title", ""), "score": round(c.get("similarity", 0.7) * 100)}
                for c in chunks
            ],
            "total": len(chunks),
        },
    }


@router.post("/policy/match")
async def policy_match(request: dict):
    eid = request.get("enterprise_id", "")
    return {
        "success": True,
        "data": {
            "enterprise_id": eid,
            "policies": [
                {"title": "广州市人工智能产业扶持办法", "match_score": 95, "level": "municipal"},
                {"title": "广东省机器人产业集群行动计划", "match_score": 88, "level": "provincial"},
            ],
            "total_matched": 2,
        },
    }


# === Industry ===
@router.post("/industry/analyze")
async def industry_analyze(request: dict):
    from app.langgraph.nodes.industry_nodes import get_industry_graph
    graph = get_industry_graph()
    state = {"task_id": f"ind-{uuid4()}", "input": request, "status": "idle", "tools_used": [], "data_sources": []}
    result = await asyncio.to_thread(graph.invoke, state)
    return {"success": True, "data": result.get("report", {})}


# === Enterprise Service ===
@router.post("/service/request")
async def service_request(request: dict):
    return {
        "success": True,
        "data": {
            "ticket_id": "ST-001",
            "status": "processing",
            "service_category": "policy_service",
            "assigned_services": [{"service": "政策服务", "agent": "PolicyAgent"}],
        },
    }


# === Dashboard ===
@router.get("/dashboard/overview")
async def dashboard_overview():
    from app.langgraph.nodes.bi_nodes import get_bi_graph
    graph = get_bi_graph()
    state = {"task_id": f"bi-{uuid4()}", "input": {"dashboard_type": "overview"}, "status": "idle"}
    result = await asyncio.to_thread(graph.invoke, state)
    return {"success": True, "data": result.get("kpi_result", {})}


# === AI Daily Report ===
@router.get("/agent/daily-report")
async def daily_report():
    return {
        "success": True,
        "data": {
            "date": date.today().isoformat(),
            "summary": "园区运营稳定，机器人产业热度上升15%，建议加大传感器方向招商力度",
            "park_metrics": {"total_enterprises": 12580, "new_today": 3, "growth_rate": "3.2%"},
            "investment": {"opportunities": 230, "contacted": 45, "signed": 12},
            "risk_alerts": [
                {"enterprise": "某智能装备公司", "level": "MEDIUM", "reason": "融资6个月未更新"},
                {"enterprise": "某科技公司", "level": "LOW", "reason": "招聘量下降20%"},
            ],
            "policy_updates": 3,
            "ai_tasks_completed": 1520,
            "recommendations": [
                "机器人传感器方向存在40%产业链缺口，建议重点突破",
                "3家企业风险上升，建议本周走访",
                "新发布2条省级产业扶持政策，可为12家企业匹配",
            ],
        },
    }


# === Agent Team Status ===
@router.get("/agent/team/status")
async def agent_team_status():
    return {
        "success": True,
        "data": {
            "agents": {
                "Supervisor": {
                    "display": "AI运营总经理",
                    "icon": "👔",
                    "status": "active",
                    "last_task": "招商策略分析",
                    "last_execution_ms": 450,
                    "tasks_today": 1520,
                    "capabilities": ["意图识别", "任务规划", "Agent调度", "结果聚合"],
                },
                "IndustryAgent": {
                    "display": "AI产业研究院",
                    "icon": "🔬",
                    "status": "idle",
                    "last_task": "机器人产业趋势分析",
                    "last_execution_ms": 2500,
                    "tasks_today": 89,
                    "capabilities": ["产业链分析", "趋势预测", "知识图谱"],
                },
                "InvestmentAgent": {
                    "display": "AI招商经理",
                    "icon": "💼",
                    "status": "idle",
                    "last_task": "企业搜索与评分",
                    "last_execution_ms": 3200,
                    "tasks_today": 230,
                    "capabilities": ["企业搜索", "企业画像", "招商评分", "策略生成"],
                },
                "RiskAgent": {
                    "display": "企业风险雷达",
                    "icon": "🛡️",
                    "status": "idle",
                    "last_task": "批量风险评估",
                    "last_execution_ms": 1800,
                    "tasks_today": 500,
                    "capabilities": ["风险评分", "舆情分析", "90天预测"],
                },
                "PolicyAgent": {
                    "display": "AI政策顾问",
                    "icon": "📋",
                    "status": "idle",
                    "last_task": "政策匹配",
                    "last_execution_ms": 1500,
                    "tasks_today": 156,
                    "capabilities": ["政策检索", "政策匹配", "申报建议"],
                },
                "BIAgent": {
                    "display": "AI数字驾驶舱",
                    "icon": "📊",
                    "status": "idle",
                    "last_task": "Dashboard数据聚合",
                    "last_execution_ms": 800,
                    "tasks_today": 200,
                    "capabilities": ["KPI计算", "可视化", "AI洞察"],
                },
            },
            "total_tasks_today": 1520,
            "active_agents": 6,
        },
    }
