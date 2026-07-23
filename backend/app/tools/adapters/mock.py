"""MockAdapter — 开发/演示环境，继承 v1.1 所有预设企业数据

保证 ENTERPRISE_DATA_SOURCE=mock 时行为与 v1.1 100% 一致。
所有 _mock_* 方法从 gateway.py 迁移至此。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import List, Optional

from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus, EnterpriseSearchResult
from app.tools.adapters.base import DataAdapter


# ═══════════════════════════════════════════
# 预设数据 — 与 v1.1 gateway.py 完全一致
# ═══════════════════════════════════════════

_PRESET_PROFILES = {
    "ENT-001": {"name": "广东博智林机器人", "industry": "建筑机器人", "location": "佛山",
                "registered_capital": "10亿", "match_reason": "建筑机器人龙头，产业协同价值高"},
    "ENT-002": {"name": "广州数控设备", "industry": "工业机器人", "location": "广州",
                "registered_capital": "5亿", "match_reason": "国产数控系统第一梯队，与园区定位高度匹配"},
    "ENT-003": {"name": "深圳汇川技术", "industry": "伺服系统/控制器", "location": "深圳",
                "registered_capital": "8亿", "match_reason": "核心零部件能力强，可补齐产业链短板"},
    "ENT-004": {"name": "大疆创新", "industry": "无人机/传感器", "location": "深圳",
                "registered_capital": "3亿", "match_reason": "传感器与飞控技术积累深厚"},
    "ENT-005": {"name": "优必选科技", "industry": "服务机器人", "location": "深圳",
                "registered_capital": "4亿", "match_reason": "人形机器人赛道领先，品牌带动效应强"},
    "risk-001": {"name": "某智能装备公司", "industry": "智能装备", "location": "广州",
                 "registered_capital": "2亿", "match_reason": "融资动态异常，建议优先核查现金流"},
    "risk-002": {"name": "某机器人科技", "industry": "工业机器人", "location": "广州",
                 "registered_capital": "1.5亿", "match_reason": "招聘量与核心人员变化需要持续跟踪"},
    "risk-003": {"name": "某新能源材料", "industry": "新能源材料", "location": "广州",
                 "registered_capital": "3亿", "match_reason": "供应商频繁变化，需排查供应链稳定性"},
    "risk-004": {"name": "某电子制造", "industry": "电子制造", "location": "广州",
                 "registered_capital": "8000万", "match_reason": "近期工商与股权结构变更较频繁"},
    "risk-005": {"name": "某AI科技", "industry": "人工智能", "location": "广州",
                 "registered_capital": "5000万", "match_reason": "存在贷款逾期信号，需评估偿债能力"},
    "risk-006": {"name": "某芯片设计", "industry": "集成电路", "location": "广州",
                 "registered_capital": "1亿", "match_reason": "营收短期下降，建议保持常规关注"},
    "risk-007": {"name": "某医疗器械", "industry": "医疗器械", "location": "广州",
                 "registered_capital": "6000万", "match_reason": "专利纠纷尚未解决，需持续观察"},
    "risk-008": {"name": "某数据服务", "industry": "数据服务", "location": "广州",
                 "registered_capital": "3000万", "match_reason": "客户集中度偏高，建议关注收入结构"},
}

_SEARCH_BASE = [
    {"enterprise_id": "ENT-001", "name": "广东博智林机器人", "industry": "建筑机器人",
     "score": 95, "location": "佛山", "registered_capital": "10亿",
     "match_reason": "碧桂园旗下，建筑机器人龙头"},
    {"enterprise_id": "ENT-002", "name": "广州数控设备", "industry": "工业机器人",
     "score": 92, "location": "广州", "registered_capital": "5亿",
     "match_reason": "国产数控系统第一梯队"},
    {"enterprise_id": "ENT-003", "name": "深圳汇川技术", "industry": "伺服系统/控制器",
     "score": 90, "location": "深圳", "registered_capital": "8亿",
     "match_reason": "伺服驱动市占率前三"},
    {"enterprise_id": "ENT-004", "name": "大疆创新", "industry": "无人机/传感器",
     "score": 88, "location": "深圳", "registered_capital": "3亿",
     "match_reason": "传感器+飞控技术积累深厚"},
    {"enterprise_id": "ENT-005", "name": "优必选科技", "industry": "服务机器人",
     "score": 87, "location": "深圳", "registered_capital": "4亿",
     "match_reason": "人形机器人赛道领先"},
]


class MockAdapter(DataAdapter):
    """开发环境默认适配器 — 使用 v1.1 预设演示数据"""

    source_name = "mock"

    # ── EnterpriseProfile ──────────────────

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        eid = str(enterprise_id)
        presets = _PRESET_PROFILES
        default = {"name": eid or "未知企业", "industry": "智能制造", "location": "广州",
                   "registered_capital": "1亿", "match_reason": "与园区重点产业方向匹配"}
        p = presets.get(eid, default)

        # 确定性评分
        base = sum(ord(c) for c in eid) % 30
        score = min(95, 70 + base)

        return EnterpriseProfile(
            enterprise_id=eid,
            name=p["name"],
            industry=p["industry"],
            location=p.get("location", "广州"),
            registered_capital=p.get("registered_capital", "1亿"),
            match_reason=p.get("match_reason", ""),
            score=score,
            financial_health="良好",
            expansion_willingness="高",
            growth_rate=18.0,
            funding_amount=500.0,
            employee_count=200,
            patents_count=45,
            data_source="mock",
            source_time=datetime.utcnow(),
            confidence_score=0.95,
            evidence=[self._make_evidence("preset", f"Mock 预设企业: {p['name']}")],
        )

    # ── Enterprise Search ──────────────────

    async def search_enterprises(
        self, query: str, industry: str = None, location: str = None, limit: int = 20
    ) -> EnterpriseSearchResult:
        results = list(_SEARCH_BASE)

        # 关键词过滤
        if query:
            q = query.lower()
            results = [e for e in results
                       if q in e.get("industry", "").lower() or q in e.get("name", "").lower()]
            if not results:
                results = list(_SEARCH_BASE)

        profiles = []
        for e in results[:limit]:
            profiles.append(EnterpriseProfile(
                enterprise_id=e["enterprise_id"],
                name=e["name"],
                industry=e["industry"],
                location=e["location"],
                registered_capital=e["registered_capital"],
                match_reason=e["match_reason"],
                score=e.get("score", 85),
                data_source="mock",
                source_time=datetime.utcnow(),
                confidence_score=0.90,
                evidence=[self._make_evidence("mock_search", f"query={query}")],
            ))

        return EnterpriseSearchResult(
            query=query, total=len(profiles), enterprises=profiles,
            data_source="mock", source_time=datetime.utcnow(), confidence_score=0.90,
        )

    # ── Risk Events ────────────────────────

    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        eid = str(enterprise_id)
        now = datetime.utcnow()

        # 预设风险事件
        all_events = [
            RiskEvent(
                event_id=f"RISK-{eid}-001", enterprise_id=eid,
                event_type="judicial", event_level="LOW",
                title="劳动合同纠纷已结案",
                description="企业与1名员工达成和解，无其他劳动纠纷",
                occurred_date="2026-05-20", source="中国裁判文书网",
                data_source="mock", source_time=now, confidence_score=0.85,
                evidence=[self._make_evidence("court_record", "案号: (2026)粤01民终1234号")],
            ),
            RiskEvent(
                event_id=f"RISK-{eid}-002", enterprise_id=eid,
                event_type="administrative", event_level="LOW",
                title="环保检查通过",
                description="2026年Q1环保例行检查达标",
                occurred_date="2026-03-15", source="生态环境局",
                data_source="mock", source_time=now, confidence_score=0.90,
                evidence=[self._make_evidence("env_report", "检查编号: HB-2026-03-15")],
            ),
        ]

        if "risk" in eid.lower():
            all_events.append(RiskEvent(
                event_id=f"RISK-{eid}-003", enterprise_id=eid,
                event_type="financial", event_level="MEDIUM",
                title="股权质押",
                description="大股东质押15%股权用于融资",
                occurred_date="2026-06-01", source="国家企业信用信息公示系统",
                data_source="mock", source_time=now, confidence_score=0.80,
                evidence=[self._make_evidence("equity_pledge", "质押登记号: GD-2026-0601")],
            ))

        # 类型过滤
        if event_type:
            all_events = [e for e in all_events if e.event_type == event_type]

        return all_events[:limit]

    # ── Business Status ─────────────────────

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        return BusinessStatus(
            enterprise_id=str(enterprise_id),
            status="normal",
            status_detail="企业存续，经营正常",
            licenses=[{"type": "营业执照", "number": "91440000MA5xxxxxx",
                       "issue_date": "2020-01-01", "expire_date": "长期", "authority": "广州市市场监管局"}],
            penalties=[],
            abnormal_count=0,
            abnormal_records=[],
            annual_report_last_year="2025",
            data_source="mock",
            source_time=datetime.utcnow(),
            confidence_score=1.0,
            evidence=[self._make_evidence("mock_status", "基于预设数据")],
        )

    # ── Scoring (保留 gateway 评分逻辑) ────

    async def compute_scoring(self, enterprise_id: str) -> dict:
        """Mock 投资评分 — 保持与 v1.1 一致的算法"""
        eid = str(enterprise_id)
        base = sum(ord(c) for c in eid) % 30
        score = min(95, 70 + base)
        return {
            "score": score,
            "level": "STRONG_RECOMMEND" if score >= 85 else "RECOMMEND",
            "reasons": ["产业链匹配度高", "技术实力突出", "扩产意愿明确"],
        }

    async def compute_risk_scoring(self, enterprise_id: str) -> dict:
        """Mock 风险评分 — 保持与 v1.1 一致的算法"""
        eid = str(enterprise_id)
        risk_score = sum(ord(c) for c in eid[-3:]) % 50 + 15
        level = "LOW" if risk_score <= 30 else ("MEDIUM" if risk_score <= 70 else "HIGH")
        return {"risk_score": risk_score, "risk_level": level}

    # ── Health Check ────────────────────────

    async def health_check(self) -> bool:
        return True
