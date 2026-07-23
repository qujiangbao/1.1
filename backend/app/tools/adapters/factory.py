"""Adapter Factory — 根据配置创建对应的 DataAdapter"""
from __future__ import annotations

import logging
from functools import lru_cache
from app.tools.adapters.base import DataAdapter
from app.tools.adapters.mock import MockAdapter
from app.tools.adapters.tianyancha import TianyanchaAdapter
from app.tools.adapters.qichacha import QichachaAdapter
from app.tools.adapters.government import GovernmentAdapter

logger = logging.getLogger(__name__)


def create_adapter(settings=None) -> DataAdapter:
    """根据配置创建数据适配器

    优先级:
    1. 配置 ENTERPRISE_DATA_SOURCE
    2. 外部 API Key 不可用 → 降级到 MockAdapter

    降级逻辑:
    - tianyancha 但无 TIANYANCHA_API_KEY → MockAdapter + WARNING
    - qichacha 但无 QICHACHA_APP_KEY → MockAdapter + WARNING
    - government → 直接启用（无需 Key，但数据受限）
    - mock → 直接 MockAdapter
    """
    if settings is None:
        from app.config import get_settings
        settings = get_settings()

    source = settings.enterprise_data_source

    if source == "tianyancha":
        if settings.tianyancha_api_key:
            logger.info("Enterprise Data Adapter: 天眼查")
            return TianyanchaAdapter(api_key=settings.tianyancha_api_key,
                                     base_url=settings.tianyancha_base_url)
        else:
            logger.warning("天眼查 API Key 为空，降级到 MockAdapter")
            return MockAdapter()

    elif source == "qichacha":
        if settings.qichacha_app_key and settings.qichacha_secret_key:
            logger.info("Enterprise Data Adapter: 企查查")
            return QichachaAdapter(app_key=settings.qichacha_app_key,
                                   secret_key=settings.qichacha_secret_key)
        else:
            logger.warning("企查查 API 未配置，降级到 MockAdapter")
            return MockAdapter()

    elif source == "government":
        logger.info("Enterprise Data Adapter: 国家企业信用信息公示系统")
        return GovernmentAdapter()

    else:
        # 默认: mock
        logger.info("Enterprise Data Adapter: Mock (演示模式)")
        return MockAdapter()


# 全局单例缓存
_adapter: DataAdapter | None = None


def get_adapter() -> DataAdapter:
    """获取当前活动的 DataAdapter 单例"""
    global _adapter
    if _adapter is None:
        _adapter = create_adapter()
    return _adapter


def reset_adapter():
    """重置适配器单例（用于测试/配置热更新）"""
    global _adapter
    _adapter = None
