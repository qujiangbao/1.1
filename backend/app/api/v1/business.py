"""Business API — 企业数据 + 政策 RAG (P0+P1)"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from app.tools.enterprise_data import get_enterprise_data_tool

router = APIRouter()


# ═══ P0: Enterprise Data Tool API ═══

@router.get("/enterprise/{enterprise_id}/profile")
async def get_enterprise_profile(enterprise_id: str):
    """获取企业完整画像
    
    Returns: EnterpriseProfile 所有字段 + data_source + confidence_score + evidence
    """
    etd = get_enterprise_data_tool()
    profile = await etd.get_profile(enterprise_id)
    return {"success": True, "data": profile.model_dump()}


@router.get("/enterprise/{enterprise_id}/risk-events")
async def get_enterprise_risk_events(
    enterprise_id: str,
    event_type: str = Query(None, description="风险类型: judicial|administrative|operation|financial|..."),
    limit: int = Query(20, ge=1, le=100),
):
    """获取企业风险事件列表
    
    每个事件包含: event_id, event_type, event_level, title, description, occurred_date, 
    source, data_source, confidence_score, evidence
    """
    etd = get_enterprise_data_tool()
    events = await etd.get_risk_events(enterprise_id, event_type, limit)
    return {
        "success": True,
        "data": {
            "enterprise_id": enterprise_id,
            "total": len(events),
            "events": [e.model_dump() for e in events],
        }
    }


@router.get("/enterprise/{enterprise_id}/status")
async def get_enterprise_business_status(enterprise_id: str):
    """获取企业经营状态
    
    Returns: status, licenses, penalties, abnormal_count, annual_report, data_source, evidence
    """
    etd = get_enterprise_data_tool()
    status = await etd.get_business_status(enterprise_id)
    return {"success": True, "data": status.model_dump()}


@router.get("/enterprise/search")
async def search_enterprises(
    query: str = Query(..., description="搜索关键词"),
    industry: str = Query(None, description="行业筛选"),
    location: str = Query(None, description="地区筛选"),
    min_capital: float = Query(None, ge=0, description="最低注册资本"),
    max_capital: float = Query(None, ge=0, description="最高注册资本"),
    sort_by: str = Query(
        "relevance",
        pattern="^(relevance|capital_desc|capital_asc)$",
        description="排序：相关度、注册资本降序或升序",
    ),
    limit: int = Query(20, ge=1, le=100),
):
    """搜索企业
    
    Returns: 匹配的企业列表，每项包含 EnterpriseProfile 字段
    """
    etd = get_enterprise_data_tool()
    result = await etd.search_enterprises(
        query,
        industry,
        location,
        limit,
        min_capital=min_capital,
        max_capital=max_capital,
        sort_by=sort_by,
    )
    return {"success": True, "data": {
        "query": result.query,
        "total": result.total,
        "enterprises": [e.model_dump() for e in result.enterprises],
        "data_source": result.data_source,
        "confidence_score": result.confidence_score,
    }}


@router.get("/enterprise/data-source")
async def get_data_source_info():
    """获取当前数据源信息"""
    etd = get_enterprise_data_tool()
    healthy = await etd.health_check()
    return {
        "success": True,
        "data": {
            "source_name": etd.source_name,
            "healthy": healthy,
            "stats": etd.stats(),
        }
    }


# ═══ P1: Policy RAG API ═══

class PolicySearchRequest(BaseModel):
    query: str
    enterprise_id: Optional[str] = None
    filters: Optional[dict] = None
    top_k: int = Field(default=10, ge=1, le=50)


class PolicyMatchRequest(BaseModel):
    enterprise_id: str
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/policy/search")
async def policy_search(body: PolicySearchRequest):
    """政策智能检索"""
    from app.tools.knowledge_tool import get_knowledge_tool
    kt = get_knowledge_tool()
    result = await kt.policy_hybrid_search({
        "query": body.query,
        "top_k": body.top_k,
        "filters": body.filters,
    })
    if result.get("status") != "success":
        raise HTTPException(status_code=503, detail=result.get("error", "Policy search unavailable"))
    return {"success": True, "data": result.get("result", result)}


@router.post("/policy/match")
async def policy_match(body: PolicyMatchRequest):
    """企业政策自动匹配 — 基于企业画像智能搜索适用政策"""
    from app.tools.knowledge_tool import get_knowledge_tool
    etd = get_enterprise_data_tool()

    # 1. 获取企业画像
    profile = await etd.get_profile(body.enterprise_id)

    # 2. 构建搜索查询
    query = " ".join(filter(None, (
        profile.industry,
        profile.location,
        " ".join(profile.tags),
        (profile.business_scope or "")[:300],
    )))
    filters = {}
    if profile.industry:
        filters["industry"] = profile.industry
    if profile.location:
        filters["region"] = profile.location

    # 3. 混合检索
    kt = get_knowledge_tool()
    result = await kt.policy_hybrid_search({
        "query": query, "top_k": body.top_k, "filters": filters,
    })
    if result.get("status") != "success":
        raise HTTPException(status_code=503, detail=result.get("error", "Policy search unavailable"))

    chunks = result.get("result", {}).get("chunks", [])
    return {
        "success": True,
        "data": {
            "enterprise_id": body.enterprise_id,
            "enterprise_name": profile.name,
            "industry": profile.industry,
            "location": profile.location,
            "matched_policies": chunks,
            "total_matched": len(chunks),
        }
    }


@router.get("/policy/rag-status")
async def get_policy_rag_status():
    """RAG 系统状态"""
    from app.config import get_settings
    s = get_settings()
    mode = s.policy_rag_mode

    total_docs = 0
    total_chunks = 0
    last_updated = None
    healthy = True
    if mode == "pgvector":
        from app.services.vector_store import VectorStore
        vs = VectorStore()
        total_chunks = await vs.count_chunks()
        healthy = total_chunks > 0
    elif mode == "crawl4ai":
        try:
            from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData
            stats = PolicyCrawl4AIData().stats()
            total_docs = stats["total_documents"]
            last_updated = stats["last_updated"]
            healthy = stats["healthy"]
        except Exception:
            healthy = False

    return {
        "success": True,
        "data": {
            "mode": mode,
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "last_updated": last_updated,
            "embedding_model": s.policy_embedding_model,
            "embedding_dimensions": s.policy_embedding_dimensions,
            "healthy": healthy,
        }
    }


# ═══ P8: Compatibility endpoints for frontend ═══

@router.post("/investment/search")
async def investment_search(body: dict):
    """P8: 兼容 POST /investment/search → 委托 EnterpriseDataTool"""
    from app.core.data_mode import require_allowed_data_mode
    data_mode = require_allowed_data_mode(body.get("data_mode"))
    if data_mode == "demo":
        from app.services.demo_scenario import (
            DEMO_DISCLAIMER,
            DEMO_INVESTMENT_TARGETS,
        )

        query = str(body.get("query", "")).strip().lower()
        candidates = [
            {
                **item,
                "location": "演示园区",
                "enterprise_status": "演示状态",
                "registered_capital": "演示字段",
                "credit_code": None,
                "patents_count": None,
                "tags": ["演示沙盘", item["industry"]],
                "match_reason": item["evidence"],
                "data_quality": {"credit_code": "synthetic"},
            }
            for item in DEMO_INVESTMENT_TARGETS
            if not query
            or query in item["name"].lower()
            or query in item["industry"].lower()
            or query in "机器人产业"
        ]
        return {
            "success": True,
            "data": {
                "enterprises": candidates,
                "total": len(candidates),
                "returned": len(candidates),
                "catalog_total": 36,
                "data_quality": {},
                "limitations": [DEMO_DISCLAIMER],
                "data_source": "demo_scenario",
                "is_demo": True,
                "disclaimer": DEMO_DISCLAIMER,
            },
        }

    from app.tools.enterprise_data import get_enterprise_data_tool
    etd = get_enterprise_data_tool()
    query = body.get("industry", body.get("query", ""))
    result = await etd.search_enterprises(
        query,
        industry=body.get("industry_filter"),
        location=body.get("location"),
        limit=body.get("limit", 20),
        min_capital=body.get("min_capital"),
        max_capital=body.get("max_capital"),
        sort_by=body.get("sort_by", "relevance"),
    )
    enterprises = [enterprise.model_dump() for enterprise in result.enterprises]
    stats = etd.stats()
    return {
        "success": True,
        "data": {
            "enterprises": enterprises,
            "total": result.total,
            "returned": len(enterprises),
            "catalog_total": stats.get("total_enterprises"),
            "data_quality": stats.get("coverage", {}),
            "limitations": stats.get("limitations", []),
            "data_source": result.data_source,
        }
    }


@router.get("/investment/profile/{enterprise_id}")
async def investment_profile(enterprise_id: str):
    """P8: 兼容 GET /investment/profile/{id} → /enterprise/{id}/profile"""
    return await get_enterprise_profile(enterprise_id)
