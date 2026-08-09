"""Adapter Factory — 根据配置创建对应的 DataAdapter"""
from __future__ import annotations

import logging
from app.tools.adapters.base import DataAdapter
from app.tools.adapters.mock import MockAdapter
from app.tools.adapters.tianyancha import TianyanchaAdapter
from app.tools.adapters.qichacha import QichachaAdapter
from app.tools.adapters.local_json import LocalJsonAdapter

logger = logging.getLogger(__name__)


def create_adapter(settings=None) -> DataAdapter:
    """根据配置创建数据适配器

    生产环境采用 fail-closed：凭据缺失或适配器未实现时直接报错，
    绝不把真实数据请求静默替换成演示数据。
    """
    if settings is None:
        from app.config import get_settings
        settings = get_settings()

    source = settings.enterprise_data_source

    if source == "local_json":
        logger.info("Enterprise Data Adapter: local JSON")
        return LocalJsonAdapter(
            settings.enterprise_local_json_path,
            include_park_documents=True,
        )

    if source == "tianyancha":
        if settings.tianyancha_api_key:
            logger.info("Enterprise Data Adapter: 天眼查")
            return TianyanchaAdapter(api_key=settings.tianyancha_api_key,
                                     base_url=settings.tianyancha_base_url)
        raise RuntimeError("TIANYANCHA_API_KEY is required for Tianyancha")

    elif source == "qichacha":
        if settings.qichacha_app_key and settings.qichacha_secret_key:
            logger.info("Enterprise Data Adapter: 企查查")
            return QichachaAdapter(app_key=settings.qichacha_app_key,
                                   secret_key=settings.qichacha_secret_key)
        raise RuntimeError(
            "QICHACHA_APP_KEY and QICHACHA_SECRET_KEY are required for Qichacha"
        )

    elif source == "government":
        raise RuntimeError(
            "Government enterprise adapter is not implemented; "
            "use local_json or a configured licensed provider"
        )

    elif source == "mock":
        if settings.app_env.lower() == "production" or not settings.enable_demo_mode:
            raise RuntimeError("Mock enterprise data is disabled")
        logger.warning("Enterprise Data Adapter: mock (development only)")
        return MockAdapter()

    else:
        raise RuntimeError(f"Unsupported enterprise data source: {source}")


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
