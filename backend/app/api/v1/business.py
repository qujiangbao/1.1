"""Business API — 企业数据查询 + 经营状态 + 风险事件 (P0)"""
from fastapi import APIRouter, Query
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
