"""QichachaAdapter — 企查查 API 适配器"""
from __future__ import annotations

from typing import List
import logging

from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus, EnterpriseSearchResult
from app.tools.adapters.base import DataAdapter

logger = logging.getLogger(__name__)


class QichachaAdapter(DataAdapter):
    """企查查开放平台 API 适配器

    API 文档: https://openapi.qcc.com
    需要: QICHACHA_APP_KEY + QICHACHA_SECRET_KEY
    """

    source_name = "qichacha"

    def __init__(self, app_key: str = "", secret_key: str = ""):
        self.app_key = app_key
        self.secret_key = secret_key
        self._available = bool(app_key and secret_key)

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        if not self._available:
            logger.warning("企查查 API 未配置，请设置 QICHACHA_APP_KEY 和 QICHACHA_SECRET_KEY")
            return self._fallback_profile(enterprise_id, "API 未配置")

        # TODO: GET /Company/GetCompanyDetail?keyNo={key}
        return self._fallback_profile(enterprise_id, "API 调用待实现")

    async def search_enterprises(
        self, query: str, industry: str = None, location: str = None, limit: int = 20
    ) -> EnterpriseSearchResult:
        if not self._available:
            logger.warning("企查查 API 未配置")
            return EnterpriseSearchResult(query=query, total=0, enterprises=[],
                                          data_source="qichacha", confidence_score=0.0)
        # TODO: GET /Company/Search?key={query}
        return EnterpriseSearchResult(query=query, total=0, enterprises=[],
                                      data_source="qichacha", confidence_score=0.0)

    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        if not self._available:
            return []
        # TODO: GET /Company/GetCompanyRiskInfo
        return []

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        if not self._available:
            return self._fallback_status(enterprise_id, "API 未配置")
        # TODO: GET /Company/GetCompanyBaseInfo
        return self._fallback_status(enterprise_id, "API 调用待实现")

    async def health_check(self) -> bool:
        if not self._available:
            return False
        try:
            return True
        except Exception:
            return False

    def _fallback_profile(self, eid: str, reason: str) -> EnterpriseProfile:
        return EnterpriseProfile(
            enterprise_id=eid, name=eid, data_source="qichacha",
            confidence_score=0.0,
            evidence=[self._make_evidence("fallback", reason)],
        )

    def _fallback_status(self, eid: str, reason: str) -> BusinessStatus:
        return BusinessStatus(
            enterprise_id=eid, data_source="qichacha",
            confidence_score=0.0,
            evidence=[self._make_evidence("fallback", reason)],
        )
