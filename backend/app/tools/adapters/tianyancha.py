"""TianyanchaAdapter — 天眼查 API 适配器"""
from __future__ import annotations

from typing import List
import logging

from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus, EnterpriseSearchResult
from app.tools.adapters.base import DataAdapter

logger = logging.getLogger(__name__)


class TianyanchaAdapter(DataAdapter):
    """天眼查商业数据 API 适配器
    
    API 文档: https://open.tianyancha.com
    需要: TIANYANCHA_API_KEY
    """

    source_name = "tianyancha"

    def __init__(self, api_key: str = "", base_url: str = "https://api.tianyancha.com"):
        self.api_key = api_key
        self.base_url = base_url
        self._available = bool(api_key)

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        if not self._available:
            logger.warning("天眼查 API Key 未配置，请设置 TIANYANCHA_API_KEY")
            return self._fallback_profile(enterprise_id, "API Key 未配置")

        # TODO: 对接真实 API
        # response = await httpx.get(f"{self.base_url}/company/v3/baseinfo",
        #     params={"keyword": enterprise_id},
        #     headers={"Authorization": self.api_key})
        return self._fallback_profile(enterprise_id, "API 调用待实现")

    async def search_enterprises(
        self, query: str, industry: str = None, location: str = None, limit: int = 20
    ) -> EnterpriseSearchResult:
        if not self._available:
            logger.warning("天眼查 API Key 未配置")
            return EnterpriseSearchResult(query=query, total=0, enterprises=[],
                                          data_source="tianyancha", confidence_score=0.0)

        # TODO: GET /search/v3/search?word={query}
        return EnterpriseSearchResult(query=query, total=0, enterprises=[],
                                      data_source="tianyancha", confidence_score=0.0)

    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        if not self._available:
            return []
        # TODO: GET /company/v3/risk?gid={id}
        return []

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        if not self._available:
            return self._fallback_status(enterprise_id, "API Key 未配置")
        # TODO: GET /company/v3/baseinfo
        return self._fallback_status(enterprise_id, "API 调用待实现")

    async def health_check(self) -> bool:
        if not self._available:
            return False
        try:
            # TODO: 真实健康检查请求
            return True
        except Exception:
            return False

    def _fallback_profile(self, eid: str, reason: str) -> EnterpriseProfile:
        return EnterpriseProfile(
            enterprise_id=eid, name=eid, data_source="tianyancha",
            confidence_score=0.0,
            evidence=[self._make_evidence("fallback", reason)],
        )

    def _fallback_status(self, eid: str, reason: str) -> BusinessStatus:
        return BusinessStatus(
            enterprise_id=eid, data_source="tianyancha",
            confidence_score=0.0,
            evidence=[self._make_evidence("fallback", reason)],
        )
