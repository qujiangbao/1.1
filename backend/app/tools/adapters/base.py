"""DataAdapter — 抽象基类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus, EnterpriseSearchResult


class DataAdapter(ABC):
    """企业数据适配器抽象基类

    所有外部数据源（天眼查/企查查/政府公示/本地Mock）必须实现此接口。
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源标识: "mock" | "tianyancha" | "qichacha" | "government" """
        ...

    @abstractmethod
    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        """获取企业画像"""
        ...

    @abstractmethod
    async def search_enterprises(
        self, query: str, industry: str = None, location: str = None, limit: int = 20
    ) -> EnterpriseSearchResult:
        """搜索企业"""
        ...

    @abstractmethod
    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        """获取风险事件列表"""
        ...

    @abstractmethod
    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        """获取经营状态"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """适配器可用性检查"""
        ...

    def _make_evidence(self, key: str, value: str, url: str = "") -> dict:
        """构造证据链条目"""
        return {"type": key, "value": value, "url": url}
