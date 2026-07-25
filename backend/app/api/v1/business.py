"""Business API — 企业数据 + 政策 RAG (P0+P1)"""
from fastapi import APIRouter, Query
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
    limit: int = Query(20, ge=1, le=100),
):
    """搜索企业
    
    Returns: 匹配的企业列表，每项包含 EnterpriseProfile 字段
    """
    etd = get_enterprise_data_tool()
    result = await etd.search_enterprises(query, industry, location, limit)
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
    result = kt.policy_hybrid_search_sync({
        "query": body.query,
        "top_k": body.top_k,
        "filters": body.filters,
    })
    return {"success": True, "data": result.get("result", result)}


@router.post("/policy/match")
async def policy_match(body: PolicyMatchRequest):
    """企业政策自动匹配 — 基于企业画像智能搜索适用政策"""
    from app.tools.knowledge_tool import get_knowledge_tool
    etd = get_enterprise_data_tool()

    # 1. 获取企业画像
    profile = await etd.get_profile(body.enterprise_id)

    # 2. 构建搜索查询
    query = f"{profile.industry or ''} {profile.location or ''}"
    filters = {}
    if profile.industry:
        filters["industry"] = profile.industry
    if profile.location:
        filters["region"] = profile.location

    # 3. 混合检索
    kt = get_knowledge_tool()
    result = kt.policy_hybrid_search_sync({
        "query": query, "top_k": body.top_k, "filters": filters,
    })

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
    if mode == "pgvector":
        from app.services.vector_store import VectorStore
        vs = VectorStore()
        total_chunks = await vs.count_chunks()

    return {
        "success": True,
        "data": {
            "mode": mode,
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "embedding_model": s.policy_embedding_model,
            "embedding_dimensions": s.policy_embedding_dimensions,
            "healthy": True,
        }
    }


# ═══ P8: Compatibility endpoints for frontend ═══

@router.post("/investment/search")
async def investment_search(body: dict):
    """P8: 兼容 POST /investment/search → 委托 EnterpriseDataTool"""
    from app.tools.enterprise_data import get_enterprise_data_tool
    etd = get_enterprise_data_tool()
    query = body.get("industry", body.get("query", ""))
    result = etd.search_enterprises_sync(query, limit=body.get("limit", 20))
    enterprises = result.get("enterprises", [])
    return {
        "success": True,
        "data": {
            "enterprises": enterprises,
            "total": len(enterprises),
            "data_source": "mock",
        }
    }


@router.get("/investment/profile/{enterprise_id}")
async def investment_profile(enterprise_id: str):
    """P8: 兼容 GET /investment/profile/{id} → /enterprise/{id}/profile"""
    return await get_enterprise_profile(enterprise_id)
