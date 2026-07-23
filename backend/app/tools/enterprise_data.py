"""EnterpriseDataTool — 企业数据统一访问工具

P0 核心模块。所有 Agent 通过此类获取真实企业数据。
内部委托给 DataAdapter（Mock/Tianyancha/Qichacha/Government）。

使用:
    from app.tools.enterprise_data import get_enterprise_data_tool
    etd = get_enterprise_data_tool()
    profile = await etd.get_profile("ENT-001")
"""
from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any

from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus, EnterpriseSearchResult
from app.tools.adapters.base import DataAdapter
from app.tools.adapters.factory import get_adapter, reset_adapter

logger = logging.getLogger(__name__)


class EnterpriseDataTool:
    """企业数据统一访问工具

    所有 Agent（RiskAgent / InvestmentAgent 等）通过此类获取企业数据，
    不直接依赖 ToolGateway 的 mock 方法。

    设计原则:
    - 单例模式，全局共享一个 Adapter
    - 同步包装异步方法以兼容 ToolGateway 同步调用
    - 异常兜底: 外部 API 异常时返回空/默认值，不阻断 Agent 流程
    """

    def __init__(self):
        self._adapter: DataAdapter | None = None

    @property
    def adapter(self) -> DataAdapter:
        if self._adapter is None:
            self._adapter = get_adapter()
        return self._adapter

    @property
    def source_name(self) -> str:
        """当前数据源名称"""
        return self.adapter.source_name

    def reset(self):
        """重置适配器（测试/配置变更时）"""
        self._adapter = None
        reset_adapter()

    # ═══ 同步包装（兼容 ToolGateway invoke 模式） ═══

    def get_profile_sync(self, enterprise_id: str) -> dict:
        """同步获取企业画像 → 返回 dict（兼容 gateway.py）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中（如 FastAPI），创建新任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.get_profile(enterprise_id))
                    profile = future.result(timeout=10)
            else:
                profile = loop.run_until_complete(self.get_profile(enterprise_id))
        except RuntimeError:
            profile = asyncio.run(self.get_profile(enterprise_id))
        except Exception as e:
            logger.error(f"get_profile_sync 失败: {e}")
            return self._error_result("enterprise_profile_get", str(e))

        return {"status": "success", "enterprise_id": profile.enterprise_id,
                "data": profile.model_dump()}

    def search_enterprises_sync(self, query: str, industry: str = None,
                                 location: str = None, limit: int = 20) -> dict:
        """同步搜索企业"""
        import asyncio
        try:
            result = asyncio.run(self.search_enterprises(query, industry, location, limit))
        except Exception as e:
            logger.error(f"search_enterprises_sync 失败: {e}")
            return self._error_result("enterprise_search", str(e))
        return {"status": "success", "total": result.total,
                "enterprises": [e.model_dump() for e in result.enterprises]}

    def get_risk_events_sync(self, enterprise_id: str, event_type: str = None,
                              limit: int = 20) -> dict:
        """同步获取风险事件"""
        import asyncio
        try:
            events = asyncio.run(self.get_risk_events(enterprise_id, event_type, limit))
        except Exception as e:
            logger.error(f"get_risk_events_sync 失败: {e}")
            return self._error_result("enterprise_risk_events", str(e))
        return {"status": "success", "total": len(events),
                "events": [e.model_dump() for e in events]}

    def get_business_status_sync(self, enterprise_id: str) -> dict:
        """同步获取经营状态"""
        import asyncio
        try:
            status = asyncio.run(self.get_business_status(enterprise_id))
        except Exception as e:
            logger.error(f"get_business_status_sync 失败: {e}")
            return self._error_result("enterprise_business_status", str(e))
        return {"status": "success", "data": status.model_dump()}

    def compute_scoring_sync(self, enterprise_id: str) -> dict:
        """同步投资评分"""
        import asyncio
        try:
            # 委托给 MockAdapter
            from app.tools.adapters.mock import MockAdapter
            if isinstance(self.adapter, MockAdapter):
                result = asyncio.run(self.adapter.compute_scoring(enterprise_id))
            else:
                # 非 mock: 基于真实数据评分
                profile = asyncio.run(self.get_profile(enterprise_id))
                score = min(95, 70 + (profile.patents_count or 0) // 5)
                result = {"score": score, "level": "STRONG_RECOMMEND" if score >= 85 else "RECOMMEND",
                          "reasons": ["数据驱动评分"]}
        except Exception as e:
            logger.error(f"compute_scoring_sync 失败: {e}")
            return self._error_result("investment_scoring", str(e))
        return {"status": "success", "score": result["score"],
                "level": result["level"], "reasons": result["reasons"]}

    # ═══ 异步方法 ═══

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        try:
            return await self.adapter.get_profile(enterprise_id)
        except Exception as e:
            logger.error(f"get_profile 异常: {e}，返回 fallback")
            return EnterpriseProfile(
                enterprise_id=enterprise_id, name=enterprise_id,
                data_source=self.source_name, confidence_score=0.0,
                evidence=[{"type": "error", "value": str(e)}],
            )

    async def search_enterprises(
        self, query: str, industry: str = None, location: str = None, limit: int = 20
    ) -> EnterpriseSearchResult:
        try:
            return await self.adapter.search_enterprises(query, industry, location, limit)
        except Exception as e:
            logger.error(f"search_enterprises 异常: {e}")
            return EnterpriseSearchResult(query=query, total=0, enterprises=[],
                                          data_source=self.source_name, confidence_score=0.0)

    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        try:
            return await self.adapter.get_risk_events(enterprise_id, event_type, limit)
        except Exception as e:
            logger.error(f"get_risk_events 异常: {e}")
            return []

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        try:
            return await self.adapter.get_business_status(enterprise_id)
        except Exception as e:
            logger.error(f"get_business_status 异常: {e}")
            return BusinessStatus(
                enterprise_id=enterprise_id, data_source=self.source_name,
                confidence_score=0.0, evidence=[{"type": "error", "value": str(e)}],
            )

    async def health_check(self) -> bool:
        try:
            return await self.adapter.health_check()
        except Exception:
            return False

    # ═══ 辅助 ═══

    def _error_result(self, tool_name: str, error_msg: str) -> dict:
        return {"status": "error", "tool": tool_name, "error": error_msg, "result": None}


# ═══ 全局单例 ═══

_etd: EnterpriseDataTool | None = None


def get_enterprise_data_tool() -> EnterpriseDataTool:
    """获取 EnterpriseDataTool 单例"""
    global _etd
    if _etd is None:
        _etd = EnterpriseDataTool()
    return _etd
