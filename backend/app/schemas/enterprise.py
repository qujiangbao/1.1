"""Enterprise Data Schemas — P0: Enterprise Data Tool

统一企业数据模型，所有 Adapter 输出的标准格式。
包含: EnterpriseProfile, RiskEvent, BusinessStatus
每个 schema 均包含 data_source / source_time / confidence_score / evidence 字段。
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
# EnterpriseProfile — 企业画像
# ═══════════════════════════════════════════

class EnterpriseProfile(BaseModel):
    """统一企业画像 — 所有 DataAdapter 输出的标准格式"""

    # ── 基础信息 ──
    enterprise_id: str = Field(..., description="企业唯一标识，如 ENT-001")
    name: str = Field(..., description="企业名称")
    credit_code: Optional[str] = Field(None, description="统一社会信用代码")
    legal_representative: Optional[str] = Field(None, description="法定代表人")
    registered_capital: Optional[str] = Field(None, description="注册资本")
    capital_amount: Optional[float] = Field(None, description="注册资本数值，用于筛选和排序")
    capital_currency: Optional[str] = Field(None, description="注册资本币种")
    established_date: Optional[str] = Field(None, description="成立日期")
    company_type: Optional[str] = Field(None, description="企业类型")
    enterprise_status: Optional[str] = Field(None, description="企业登记状态")

    # ── 经营信息 ──
    industry: Optional[str] = Field(None, description="所属行业")
    industry_code: Optional[str] = Field(None, description="行业代码 GB/T 4754")
    business_scope: Optional[str] = Field(None, description="经营范围")
    address: Optional[str] = Field(None, description="注册地址")
    location: Optional[str] = Field(None, description="所在城市/区域")
    employee_count: Optional[int] = Field(None, description="参保人数")
    revenue_level: Optional[str] = Field(None, description="营收规模 A/B/C/D/E")
    growth_rate: Optional[float] = Field(None, description="年增长率 %")
    funding_stage: Optional[str] = Field(None, description="融资阶段")
    funding_amount: Optional[float] = Field(None, description="融资金额(万元)")

    # ── 扩展字段 ──
    score: Optional[int] = Field(None, description="投资评分 0-100")
    patents_count: Optional[int] = Field(None, description="专利数量")
    trademarks_count: Optional[int] = Field(None, description="商标数量")
    website: Optional[str] = Field(None, description="官网")
    contact: Optional[str] = Field(None, description="联系方式")
    match_reason: Optional[str] = Field(None, description="匹配理由")
    financial_health: Optional[str] = Field(None, description="财务健康度")
    expansion_willingness: Optional[str] = Field(None, description="扩产意愿")
    tags: List[str] = Field(default_factory=list, description="企业标签")
    data_quality: Dict[str, Any] = Field(
        default_factory=dict,
        description="字段覆盖和缺失说明；unknown 不等同于 0",
    )

    # ── 元数据 ──
    data_source: str = Field(default="mock", description="数据来源: mock|tianyancha|qichacha|government")
    source_time: Optional[datetime] = Field(default_factory=datetime.utcnow, description="数据获取时间")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="数据可信度 0-1")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="数据来源证据链")


# ═══════════════════════════════════════════
# RiskEvent — 风险事件
# ═══════════════════════════════════════════

class RiskEvent(BaseModel):
    """单条企业风险事件"""

    event_id: str = Field(..., description="事件唯一标识，如 RISK-2026-001")
    enterprise_id: str = Field(..., description="关联企业 ID")
    event_type: str = Field(..., description="风险类型: judicial|administrative|operation|financial|credit|tax|equity|executive|public_opinion|other")
    event_level: str = Field(default="MEDIUM", description="风险等级: HIGH|MEDIUM|LOW")
    title: str = Field(..., description="事件标题")
    description: Optional[str] = Field(None, description="详细描述")
    occurred_date: Optional[str] = Field(None, description="发生日期")
    source: str = Field(..., description="原始数据来源")
    source_url: Optional[str] = Field(None, description="原文链接")

    # ── 元数据 ──
    data_source: str = Field(default="mock", description="通过哪个 Adapter 获取")
    source_time: Optional[datetime] = Field(default_factory=datetime.utcnow, description="数据获取时间")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="事件可信度")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="证据: [{type, value, url}]")


# ═══════════════════════════════════════════
# BusinessStatus — 经营状态
# ═══════════════════════════════════════════

class BusinessStatus(BaseModel):
    """企业经营状态"""

    enterprise_id: str
    status: str = Field(default="normal", description="normal|abnormal|revoked|cancelled")
    status_detail: Optional[str] = Field(None, description="状态详情说明")

    # ── 行政许可 ──
    licenses: List[Dict[str, Any]] = Field(default_factory=list,
        description="[{type, number, issue_date, expire_date, authority}]")

    # ── 行政处罚 ──
    penalties: List[Dict[str, Any]] = Field(default_factory=list,
        description="[{reason, amount, date, authority}]")

    # ── 经营异常 ──
    abnormal_count: int = Field(default=0, description="经营异常记录数")
    abnormal_records: List[Dict[str, Any]] = Field(default_factory=list,
        description="[{date, reason, removal_date}]")

    # ── 年报 ──
    annual_report_last_year: Optional[str] = Field(None, description="最近年报年份")

    # ── 元数据 ──
    data_source: str = Field(default="mock")
    source_time: Optional[datetime] = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


# ═══════════════════════════════════════════
# EnterpriseSearchResult — 企业搜索结果
# ═══════════════════════════════════════════

class EnterpriseSearchResult(BaseModel):
    """企业搜索结果"""
    query: str
    total: int
    enterprises: List[EnterpriseProfile]
    data_source: str = "mock"
    source_time: Optional[datetime] = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=0.9)
