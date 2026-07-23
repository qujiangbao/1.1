# Enterprise Data Tool — Technical Design V1.0

> **文档**: P0 Technical Design Review  
> **版本**: v1.0  
> **基准**: v1.1 Competition Gold  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-23

---

## 目录

1. [设计目标](#1-设计目标)
2. [Enterprise 统一数据 Schema](#2-enterprise-统一数据-schema)
3. [Data Adapter 设计](#3-data-adapter-设计)
4. [Tool Gateway 调用协议](#4-tool-gateway-调用协议)
5. [Mock/Real 双模式切换](#5-mockreal-双模式切换)
6. [API 接口定义](#6-api-接口定义)
7. [文件结构](#7-文件结构)
8. [与现存代码的集成点](#8-与现存代码的集成点)

---

## 1. 设计目标

将 RiskAgent 的数据源从硬编码 Mock 升级为**可插拔的多源企业数据适配器**，支持：

- **开发环境**: Mock 适配器（现有逻辑保留在适配器内）
- **生产环境**: 天眼查 / 企查查 / 国家企业信用信息公示系统
- **切换方式**: 配置项驱动，零代码改动

关键约束：
- 不破坏 ToolGateway 现有接口签名
- RiskAgent graph 的 7 节点 Pipeline 结构不变
- `DATABASE_ENABLED=false` 时完全可用

---

## 2. Enterprise 统一数据 Schema

### 2.1 EnterpriseProfile（企业画像）

```python
# backend/app/schemas/enterprise.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EnterpriseProfile(BaseModel):
    """统一企业画像 — 所有 Adapter 输出的标准格式"""

    # === 基础信息 (来自 Enterprise 表) ===
    enterprise_id: str                    # ENT-001
    name: str                            # 企业名称
    credit_code: Optional[str] = None     # 统一社会信用代码
    legal_representative: Optional[str] = None  # 法定代表人
    registered_capital: Optional[str] = None    # 注册资本
    established_date: Optional[str] = None      # 成立日期
    company_type: Optional[str] = None    # 企业类型 (有限责任公司等)

    # === 经营信息 (来自 EnterpriseProfile 表) ===
    industry: Optional[str] = None        # 所属行业
    industry_code: Optional[str] = None   # 行业代码 (GB/T 4754)
    business_scope: Optional[str] = None  # 经营范围
    address: Optional[str] = None         # 注册地址
    employee_count: Optional[int] = None  # 参保人数
    revenue_level: Optional[str] = None   # 营收规模 (A-E)
    growth_rate: Optional[float] = None   # 年增长率 %
    funding_stage: Optional[str] = None   # 融资阶段

    # === 扩展字段 (外部 API) ===
    patents_count: Optional[int] = None   # 专利数量
    trademarks_count: Optional[int] = None # 商标数量
    website: Optional[str] = None         # 官网
    contact: Optional[str] = None         # 联系方式

    # === 元数据 ===
    data_source: str                      # "tianyancha" | "qichacha" | "government" | "mock"
    updated_at: Optional[datetime] = None # 数据更新时间
```

### 2.2 RiskEvent（风险事件）

```python
class RiskEvent(BaseModel):
    """单条风险事件"""

    event_id: str                        # RISK-2026-001
    enterprise_id: str                   # 关联企业
    event_type: str                      # 风险类型枚举
    event_level: str                     # HIGH | MEDIUM | LOW
    title: str                           # 事件标题
    description: Optional[str] = None    # 详细描述
    occurred_date: Optional[str] = None  # 发生日期
    source: str                          # 数据来源
    source_url: Optional[str] = None     # 原文链接
    data_source: str                     # "tianyancha" | "qichacha" | ...

    # 风险类型枚举
    class EventType:
        JUDICIAL = "judicial"            # 司法风险 (开庭公告/裁判文书)
        ADMINISTRATIVE = "administrative" # 行政处罚
        OPERATION = "operation"          # 经营异常
        FINANCIAL = "financial"          # 财务风险 (股权冻结/质押)
        CREDIT = "credit"                # 失信被执行人
        TAX = "tax"                      # 税务异常
        EQUITY = "equity"                # 股权变更
        EXECUTIVE = "executive"          # 高管变动
        PUBLIC_OPINION = "public_opinion" # 舆论风险
        OTHER = "other"
```

### 2.3 BusinessStatus（经营状态）

```python
class BusinessStatus(BaseModel):
    """企业经营状态"""

    enterprise_id: str
    status: str                          # normal | abnormal | revoked | cancelled
    status_detail: Optional[str] = None  # 状态详情

    # 行政许可
    licenses: List[dict] = []            # [{type, number, expire_date}]

    # 行政处罚
    penalties: List[dict] = []           # [{reason, amount, date, authority}]

    # 异常经营
    abnormal_count: int = 0              # 经营异常记录数

    # 年报
    annual_report_last_year: Optional[str] = None  # 最近年报年份

    data_source: str
    updated_at: Optional[datetime] = None
```

### 2.4 与现有 SQLAlchemy 模型的映射

```
EnterpriseProfile (Pydantic)          Enterprise + EnterpriseProfile (SQLAlchemy)
─────────────────────────────         ──────────────────────────────────────────
enterprise_id                      ←  Enterprise.enterprise_id
name                               ←  Enterprise.name
credit_code                        ←  Enterprise.credit_code
industry                           ←  Industry.name (JOIN)
business_scope                     ←  EnterpriseProfile.business_scope
employee_count                     ←  EnterpriseProfile.employee_count
growth_rate                        ←  EnterpriseProfile.growth_rate
funding_stage                      ←  EnterpriseProfile.funding_stage
legal_representative               ←  外部 API 补充 ⚡
patents_count                      ←  外部 API 补充 ⚡
risk_profile                       ←  外部 API → RiskEvent[] ⚡
```

---

## 3. Data Adapter 设计

### 3.1 适配器架构

```
                    ┌─────────────────────┐
                    │  EnterpriseDataTool  │  ← 统一入口
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │   DataAdapter       │  ← 抽象基类 (ABC)
                    │   (Abstract)        │
                    └─────────┬───────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────▼──────┐  ┌────────▼───────┐  ┌────────▼─────────┐
│ Tianyancha     │  │ Qichacha       │  │ Government       │
│ Adapter        │  │ Adapter        │  │ Adapter          │
│                │  │                │  │ (国家公示系统)      │
└────────────────┘  └────────────────┘  └──────────────────┘
          │                   │                   │
┌─────────▼──────┐  ┌────────▼───────┐  ┌────────▼─────────┐
│ 天眼查 API      │  │ 企查查 API     │  │ gsxt.gov.cn      │
└────────────────┘  └────────────────┘  └──────────────────┘

┌─────────────────────────────────────┐
│         MockAdapter                 │  ← 继承现有 mock 数据
│         (开发环境默认)                │
└─────────────────────────────────────┘
```

### 3.2 抽象基类

```python
# backend/app/tools/adapters/base.py

from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.enterprise import EnterpriseProfile, RiskEvent, BusinessStatus


class DataAdapter(ABC):
    """企业数据适配器抽象基类"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源标识: "tianyancha" | "qichacha" | "government" | "mock" """
        ...

    @abstractmethod
    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        """获取企业画像"""
        ...

    @abstractmethod
    async def search_enterprises(self, query: str, **filters) -> List[EnterpriseProfile]:
        """搜索企业"""
        ...

    @abstractmethod
    async def get_risk_events(
        self, enterprise_id: str, event_type: Optional[str] = None,
        limit: int = 20
    ) -> List[RiskEvent]:
        """获取风险事件"""
        ...

    @abstractmethod
    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        """获取经营状态"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """适配器可用性检查"""
        ...
```

### 3.3 天眼查适配器

```python
# backend/app/tools/adapters/tianyancha.py

class TianyanchaAdapter(DataAdapter):
    source_name = "tianyancha"

    def __init__(self, api_key: str, base_url: str = "https://api.tianyancha.com"):
        self.api_key = api_key
        self.base_url = base_url

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        """
        API: GET /search/v3/base?keyword={name}
        映射: company → EnterpriseProfile
        """
        ...

    async def search_enterprises(self, query: str, **filters) -> List[EnterpriseProfile]:
        """
        API: GET /search/v3/search?word={query}&pageSize=20
        """
        ...

    async def get_risk_events(self, enterprise_id: str, ...) -> List[RiskEvent]:
        """
        API: GET /company/v3/risk?gid={company_id}
        返回: 司法风险 + 经营风险 + 行政处罚
        """
        ...

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        """
        API: GET /company/v3/baseinfo?gid={company_id}
        """
        ...
```

### 3.4 企查查适配器

```python
# backend/app/tools/adapters/qichacha.py

class QichachaAdapter(DataAdapter):
    source_name = "qichacha"

    def __init__(self, app_key: str, secret_key: str):
        ...

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        """
        API: GET /Company/GetCompanyDetail?keyNo={key}
        """
        ...

    async def search_enterprises(self, query: str, ...) -> List[EnterpriseProfile]:
        """
        API: GET /Company/Search?key={query}
        """
        ...

    async def get_risk_events(self, enterprise_id: str, ...) -> List[RiskEvent]:
        """
        API: GET /Company/GetCompanyRiskInfo?keyNo={key}
        """
        ...

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        """
        API: GET /Company/GetCompanyBaseInfo?keyNo={key}
        """
        ...
```

### 3.5 政府数据适配器

```python
# backend/app/tools/adapters/government.py

class GovernmentAdapter(DataAdapter):
    source_name = "government"

    def __init__(self):
        self.base_url = "https://api.gsxt.gov.cn"  # 或本地数据同步

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        """
        数据源: 国家企业信用信息公示系统
        特点: 免费、权威、但信息维度少
        补充: 工商注册信息、行政处罚、经营异常
        """
        ...

    async def search_enterprises(self, query: str, ...) -> List[EnterpriseProfile]:
        """通过统一社会信用代码或企业名称查询"""
        ...

    async def get_risk_events(self, enterprise_id: str, ...) -> List[RiskEvent]:
        """行政处罚 + 经营异常 + 严重违法失信"""
        ...

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        """登记状态 + 行政处罚 + 异常名录"""
        ...
```

### 3.6 Mock 适配器（迁移现有 Mock 数据）

```python
# backend/app/tools/adapters/mock.py

class MockAdapter(DataAdapter):
    source_name = "mock"

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        """
        迁移 gateway.py 中 _mock_enterprise_profile() 的逻辑
        8 个预设企业 (ENT-001 ~ ENT-005, risk-001 ~ risk-008)
        """
        ...

    async def search_enterprises(self, query: str, ...) -> List[EnterpriseProfile]:
        """
        迁移 _mock_enterprise_search() 逻辑
        5 个机器人产业链企业的搜索 + 关键词过滤
        """
        ...

    async def get_risk_events(self, enterprise_id: str, ...) -> List[RiskEvent]:
        """返回模拟风险事件数据"""
        ...

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        """返回模拟经营状态"""
        ...
```

### 3.7 适配器工厂

```python
# backend/app/tools/adapters/factory.py

from app.config import get_settings
from app.tools.adapters.base import DataAdapter
from app.tools.adapters.mock import MockAdapter
from app.tools.adapters.tianyancha import TianyanchaAdapter
from app.tools.adapters.qichacha import QichachaAdapter
from app.tools.adapters.government import GovernmentAdapter


def create_adapter() -> DataAdapter:
    settings = get_settings()
    source = settings.enterprise_data_source  # "mock" | "tianyancha" | "qichacha" | "government"

    if source == "mock":
        return MockAdapter()
    elif source == "tianyancha":
        return TianyanchaAdapter(api_key=settings.tianyancha_api_key)
    elif source == "qichacha":
        return QichachaAdapter(app_key=settings.qichacha_app_key, secret_key=settings.qichacha_secret_key)
    elif source == "government":
        return GovernmentAdapter()
    else:
        raise ValueError(f"Unknown data source: {source}")
```

---

## 4. Tool Gateway 调用协议

### 4.1 调用链路

```
User Query: "分析广州数控的风险"
    ↓
Supervisor (graph.py)
    ↓ intent="risk_single" → INTENT_ROUTING → "RiskAgent"
    ↓
Agent Router (supervisor_nodes.py)
    ↓ agent_router_node()
    ↓
Business Agent Executor (executor.py)
    ↓ execute_business_agent("RiskAgent", task, state)
    ↓
RiskAgent Graph (risk_nodes.py)
    ↓ data_request_node()
    ↓
ToolGateway.invoke("RiskAgent", "enterprise_profile_get", {enterprise_id})
    ↓
EnterpriseDataTool.get_profile(enterprise_id)
    ↓
DataAdapter.get_profile(enterprise_id)  ← 多态分发
    ↓
TianyanchaAdapter / MockAdapter / ...
    ↓
Return: EnterpriseProfile (Pydantic)
```

### 4.2 Tool Gateway 新增工具注册

```python
# gateway.py — PERMISSIONS 扩展 + Tool 注册

PERMISSIONS = {
    ...
    "RiskAgent": [
        "enterprise_query",        # [保留] 基础企业查询
        "enterprise_profile_get",  # [升级] → EnterpriseDataTool
        "risk_scoring",            # [保留] 风险评分
        "risk_history",            # [升级] → EnterpriseDataTool
        # === 新增 ===
        "enterprise_risk_events",  # [新增] 风险事件列表
        "enterprise_business_status", # [新增] 经营状态
    ],
    ...
}
```

### 4.3 调用时序图

```
RiskAgent.data_request_node()
    │
    ├─► tg.invoke("RiskAgent", "enterprise_profile_get", {enterprise_id})
    │     └─► EnterpriseDataTool.get_profile()
    │           └─► adapter.get_profile() → EnterpriseProfile
    │
    ├─► tg.invoke("RiskAgent", "enterprise_risk_events", {enterprise_id, limit: 20})
    │     └─► EnterpriseDataTool.get_risk_events()
    │           └─► adapter.get_risk_events() → List[RiskEvent]
    │
    └─► tg.invoke("RiskAgent", "enterprise_business_status", {enterprise_id})
          └─► EnterpriseDataTool.get_business_status()
                └─► adapter.get_business_status() → BusinessStatus
```

### 4.4 数据流输出到 RiskAgent

```python
# risk_nodes.py — data_request_node() 改造后

def data_request_node(state: RiskState) -> RiskState:
    eid = state["enterprise_id"]
    etd = get_enterprise_data_tool()

    # 1. 企业画像
    profile = etd.get_profile(eid)
    state["profile_data"] = profile.model_dump()  # Pydantic → dict

    # 2. 风险事件
    events = etd.get_risk_events(eid, limit=20)
    state["risk_events"] = [e.model_dump() for e in events]

    # 3. 经营状态
    status = etd.get_business_status(eid)
    state["business_status"] = status.model_dump()

    state["data_sources"] = [profile.data_source]
    state["status"] = "extracting"
    return state
```

### 4.5 EnterpriseDataTool 核心类

```python
# backend/app/tools/enterprise_data.py

from functools import lru_cache
from app.tools.adapters.factory import create_adapter
from app.tools.adapters.base import DataAdapter


class EnterpriseDataTool:
    """企业数据统一访问工具 — 所有 Agent 通过此类获取真实企业数据"""

    def __init__(self):
        self._adapter: DataAdapter | None = None

    @property
    def adapter(self) -> DataAdapter:
        if self._adapter is None:
            self._adapter = create_adapter()
        return self._adapter

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        return await self.adapter.get_profile(enterprise_id)

    async def search_enterprises(self, query: str, **filters) -> List[EnterpriseProfile]:
        return await self.adapter.search_enterprises(query, **filters)

    async def get_risk_events(
        self, enterprise_id: str, event_type: str = None, limit: int = 20
    ) -> List[RiskEvent]:
        return await self.adapter.get_risk_events(enterprise_id, event_type, limit)

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        return await self.adapter.get_business_status(enterprise_id)

    async def health_check(self) -> bool:
        return await self.adapter.health_check()


# 单例
_etd: EnterpriseDataTool | None = None

def get_enterprise_data_tool() -> EnterpriseDataTool:
    global _etd
    if _etd is None:
        _etd = EnterpriseDataTool()
    return _etd
```

---

## 5. Mock/Real 双模式切换

### 5.1 配置项

```bash
# .env / .env.example 新增

# === Enterprise Data Source ===
# mock       — 开发环境，使用预设演示数据
# tianyancha — 天眼查 API
# qichacha   — 企查查 API
# government — 国家企业信用信息公示系统
ENTERPRISE_DATA_SOURCE=mock

# 天眼查
TIANYANCHA_API_KEY=
TIANYANCHA_BASE_URL=https://api.tianyancha.com

# 企查查
QICHACHA_APP_KEY=
QICHACHA_SECRET_KEY=

# 数据缓存 (防止 API 频繁调用)
ENTERPRISE_CACHE_TTL=3600  # 缓存 1 小时
```

### 5.2 config.py 扩展

```python
class Settings(BaseSettings):
    ...
    # Enterprise Data
    enterprise_data_source: str = "mock"
    tianyancha_api_key: str = ""
    tianyancha_base_url: str = "https://api.tianyancha.com"
    qichacha_app_key: str = ""
    qichacha_secret_key: str = ""
    enterprise_cache_ttl: int = 3600
```

### 5.3 切换逻辑

```
ENTERPRISE_DATA_SOURCE=mock              → MockAdapter       (开发/演示)
ENTERPRISE_DATA_SOURCE=tianyancha        → TianyanchaAdapter (生产-天眼查)
ENTERPRISE_DATA_SOURCE=qichacha          → QichachaAdapter   (生产-企查查)
ENTERPRISE_DATA_SOURCE=government        → GovernmentAdapter (生产-政府公开数据)

如果 ENTERPRISE_DATA_SOURCE 不是 mock 但 API Key 为空:
    → 打印 WARNING，自动降级为 MockAdapter
```

### 5.4 缓存策略

```python
# EnterpriseDataTool 内置 Redis 缓存
async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
    cache_key = f"ent:profile:{enterprise_id}"
    cached = await redis.get(cache_key)
    if cached:
        return EnterpriseProfile.model_validate_json(cached)

    result = await self.adapter.get_profile(enterprise_id)
    await redis.setex(cache_key, settings.enterprise_cache_ttl, result.model_dump_json())
    return result
```

---

## 6. API 接口定义

### 6.1 新增 API 端点

```python
# backend/app/api/v1/business.py — 扩展

# === 企业数据 API ===

@router.get("/enterprise/{enterprise_id}/profile")
async def get_enterprise_profile(enterprise_id: str):
    """
    获取企业完整画像
    
    Response:
    {
      "success": true,
      "data": {
        "enterprise_id": "ENT-001",
        "name": "广东博智林机器人",
        "industry": "建筑机器人",
        "risk_summary": { "score": 35, "level": "LOW" },
        "patents_count": 120,
        "data_source": "tianyancha"
      }
    }
    """
    ...

@router.get("/enterprise/{enterprise_id}/risk-events")
async def get_enterprise_risk_events(
    enterprise_id: str,
    event_type: str = None,
    limit: int = 20
):
    """
    获取企业风险事件列表
    
    Response:
    {
      "success": true,
      "data": {
        "enterprise_id": "ENT-001",
        "total": 5,
        "events": [
          {
            "event_id": "RISK-2026-001",
            "event_type": "judicial",
            "event_level": "MEDIUM",
            "title": "劳动合同纠纷开庭公告",
            "occurred_date": "2026-06-15",
            "source": "中国裁判文书网",
          }
        ]
      }
    }
    """
    ...

@router.get("/enterprise/{enterprise_id}/status")
async def get_enterprise_business_status(enterprise_id: str):
    """
    获取企业经营状态
    
    Response:
    {
      "success": true,
      "data": {
        "status": "normal",
        "penalties": [],
        "abnormal_count": 0,
        "data_source": "government"
      }
    }
    """
    ...

@router.get("/enterprise/search")
async def search_enterprises(
    query: str,
    industry: str = None,
    location: str = None,
    limit: int = 20,
):
    """
    搜索企业
    
    Response:
    {
      "success": true,
      "data": {
        "query": "机器人",
        "total": 5,
        "enterprises": [...]
      }
    }
    """
    ...
```

### 6.2 API 路由注册

```python
# app/api/v1/__init__.py — 已有 business.router
# business.py 扩展上述 4 个端点即可
```

---

## 7. 文件结构

```
backend/
├── app/
│   ├── schemas/
│   │   └── enterprise.py          ← 新增: EnterpriseProfile, RiskEvent, BusinessStatus
│   │
│   ├── tools/
│   │   ├── gateway.py             ← 修改: 替换 mock → EnterpriseDataTool
│   │   ├── enterprise_data.py     ← 新增: EnterpriseDataTool 核心类
│   │   │
│   │   └── adapters/              ← 新增: 适配器目录
│   │       ├── __init__.py
│   │       ├── base.py            ← DataAdapter 抽象基类
│   │       ├── mock.py            ← MockAdapter (迁移现有 mock 数据)
│   │       ├── tianyancha.py      ← TianyanchaAdapter
│   │       ├── qichacha.py        ← QichachaAdapter
│   │       ├── government.py      ← GovernmentAdapter
│   │       └── factory.py         ← create_adapter() 工厂函数
│   │
│   ├── langgraph/nodes/
│   │   └── risk_nodes.py          ← 修改: data_request_node 对接 EnterpriseDataTool
│   │
│   ├── api/v1/
│   │   └── business.py            ← 修改: 新增 4 个 API 端点
│   │
│   ├── database/models/
│   │   └── business.py            ← 可能修改: 新增 RiskEvent 表 (P5 时)
│   │
│   └── config.py                  ← 修改: 新增 5 个数据源配置项
│
└── .env.example                   ← 修改: 新增数据源配置
```

### 变更统计

| 操作 | 文件数 | 行数估算 |
|------|--------|---------|
| 新增 | 8 | ~900 |
| 修改 | 5 | ~150 |
| **合计** | **13** | **~1,050** |

---

## 8. 与现存代码的集成点

### 8.1 ToolGateway 改动范围（最小化）

```diff
# gateway.py — 仅改动 _register_builtin_tools()

  def _register_builtin_tools(self):
      self._tools = {
-         "enterprise_search":       self._mock_enterprise_search,
-         "enterprise_profile_get":  self._mock_enterprise_profile,
-         "enterprise_query":        self._mock_enterprise_query,
+         "enterprise_search":       self._enterprise_search,
+         "enterprise_profile_get":  self._enterprise_profile_get,
+         "enterprise_query":        self._enterprise_query,
+         "enterprise_risk_events":  self._enterprise_risk_events,
+         "enterprise_business_status": self._enterprise_business_status,
          ...
      }

+ # 新增方法（委托给 EnterpriseDataTool）
+ def _enterprise_profile_get(self, params): ...
+ def _enterprise_search(self, params): ...
+ def _enterprise_risk_events(self, params): ...
+ def _enterprise_business_status(self, params): ...

  # 保留 _mock_* 方法 — 搬迁到 adapters/mock.py
```

### 8.2 RiskAgent Nodes 改动范围

```diff
# risk_nodes.py — data_request_node()

  def data_request_node(state: RiskState) -> RiskState:
      eid = state["enterprise_id"]
-     profile = tg.invoke("RiskAgent", "enterprise_profile_get", {"enterprise_id": eid})
-     basic = tg.invoke("RiskAgent", "enterprise_query", {"enterprise_id": eid})
+     profile = tg.invoke("RiskAgent", "enterprise_profile_get", {"enterprise_id": eid})
+     risk_events = tg.invoke("RiskAgent", "enterprise_risk_events", {"enterprise_id": eid})
+     biz_status = tg.invoke("RiskAgent", "enterprise_business_status", {"enterprise_id": eid})

      state["basic_info"] = basic.data or {}
      state["profile_data"] = profile.data or {}
+     state["risk_events"] = risk_events.data or []
+     state["business_status"] = biz_status.data or {}
      ...
```

### 8.3 RiskState 扩展

```diff
  class RiskState(TypedDict):
      ...
+     risk_events: Optional[List[Dict]]
+     business_status: Optional[Dict]
      risk_features: Optional[Dict]
      ...
```

### 8.4 向后兼容性保证

| 场景 | 行为 |
|------|------|
| `ENTERPRISE_DATA_SOURCE=mock` (默认) | 使用 MockAdapter — 完全兼容 v1.1 |
| `ENTERPRISE_DATA_SOURCE=tianyancha` + API key | 使用天眼查 |
| 外部 API 不可用 | 降级到 MockAdapter + 打印 WARNING |
| `DATABASE_ENABLED=false` | EnterpriseDataTool 正常工作（内存模式） |
| ToolGateway 其他 Agent 调用 | 不受影响（Permission 矩阵独立） |

---

## 9. 验收清单

- [ ] `EnterpriseDataTool.get_profile("ENT-001")` 返回有效 EnterpriseProfile
- [ ] `EnterpriseDataTool.get_risk_events("ENT-001")` 返回 List[RiskEvent]
- [ ] `MockAdapter` 返回与 v1.1 一致的数据结构
- [ ] `ENTERPRISE_DATA_SOURCE=mock` 时行为与 v1.1 完全相同
- [ ] `ENTERPRISE_DATA_SOURCE=tianyancha` + 无效 key → 降级到 mock
- [ ] RiskAgent 7 节点 Pipeline 全部通过
- [ ] API `/enterprise/{id}/profile` 返回正确 JSON
- [ ] `DATABASE_ENABLED=false` 时不报错
- [ ] 现有 5 个 Demo 测试仍然通过

---

*Generated by Hermes Agent · 2026-07-23 · Enterprise Data Tool Design V1.0*
