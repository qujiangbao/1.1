"""GovernmentAdapter — 国家企业信用信息公示系统适配器"""
from __future__ import annotations

from typing import List
import logging

from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus, EnterpriseSearchResult
from app.tools.adapters.base import DataAdapter

logger = logging.getLogger(__name__)


class GovernmentAdapter(DataAdapter):
    """国家企业信用信息公示系统适配器

    数据源: https://www.gsxt.gov.cn
    特点: 免费、权威、工商/行政处罚/经营异常信息
    限制: 无 API 公开接口，需爬虫或本地数据同步
    """

    source_name = "government"

    def __init__(self):
        self._available = False  # 待数据同步方案确定后启用

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        logger.info("政府数据适配器尚未启用，返回 fallback")
        return EnterpriseProfile(
            enterprise_id=enterprise_id, name=enterprise_id, data_source="government",
            confidence_score=0.3,
            evidence=[self._make_evidence("fallback", "数据同步方案待确定")],
        )

    async def search_enterprises(
        self, query: str, industry: str = None, location: str = None, limit: int = 20
    ) -> EnterpriseSearchResult:
        return EnterpriseSearchResult(
            query=query, total=0, enterprises=[],
            data_source="government", confidence_score=0.0,
        )

    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        return []

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        return BusinessStatus(
            enterprise_id=enterprise_id, data_source="government",
            confidence_score=0.3,
            evidence=[self._make_evidence("fallback", "数据同步方案待确定")],
        )

    async def health_check(self) -> bool:
        return False  # 未启用
