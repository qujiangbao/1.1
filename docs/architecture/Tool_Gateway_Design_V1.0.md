# Industrial Park Agent
# Tool Gateway Design V1.0

> 版本：V1.0 | 状态：FROZEN
> 
> Tool Gateway 是系统中所有工具调用的唯一入口。
> 所有 Agent 必须通过 Tool Gateway 访问数据库、RAG、外部 API 等资源。

---

## 1. 核心原则

```
禁止：Agent → Database / RAG / External API
正确：Agent → Supervisor → Tool Gateway → Tool → Resource → Return
```

### 为什么需要 Tool Gateway

| 原因 | 说明 |
|------|------|
| 可追踪 | 每次工具调用都被完整记录 |
| 可审计 | 谁、何时、调了什么、结果如何 |
| 可控制 | 权限校验、速率限制、参数验证 |
| 可替换 | Tool 实现可独立升级，不影响 Agent |
| 可解释 | Agent Trace 包含完整的数据来源链路 |

---

## 2. Tool 分类体系

```
Tool Gateway
  |
  ├── Data Tools (数据工具)
  │   ├── enterprise_query         企业查询
  │   ├── enterprise_search        企业搜索
  │   ├── enterprise_profile_get   企业画像获取
  │   ├── industry_query           产业查询
  │   ├── policy_query             政策查询
  │   └── risk_query               风险查询
  │
  ├── Knowledge Tools (知识工具)
  │   ├── policy_vector_search     政策 RAG 检索
  │   ├── industry_vector_search   产业 RAG 检索
  │   ├── enterprise_vector_search 企业语义搜索
  │   ├── policy_metadata_search   政策条件过滤
  │   └── knowledge_graph_query    知识图谱查询
  │
  ├── Analysis Tools (分析工具)
  │   ├── risk_scoring             风险评分计算
  │   ├── investment_scoring       招商评分计算
  │   ├── policy_match_scoring     政策匹配评分
  │   ├── industry_trend_score     产业趋势评分
  │   └── report_generator         报告生成
  │
  ├── Memory Tools (记忆工具)
  │   ├── memory_save              保存记忆
  │   ├── memory_search            搜索记忆
  │   └── memory_context_load      加载上下文
  │
  └── External Tools (外部工具)
      ├── web_search               网络搜索
      ├── news_sentiment           舆情分析
      └── geo_query                地理查询
```

---

## 3. Tool 标准定义

每个 Tool 必须实现以下接口：

```python
from typing import Dict, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class ToolDefinition:
    """工具定义"""
    name: str                           # 工具唯一名称
    category: str                       # 分类: data / knowledge / analysis / memory / external
    description: str                    # 工具描述（给 LLM 看的）
    parameters: Dict[str, Any]          # JSON Schema 参数定义
    returns: Dict[str, Any]             # 返回值 Schema
    permissions: List[str]              # 哪些 Agent 可以调用
    rate_limit: int                     # 每秒最大调用次数
    timeout_ms: int                     # 超时时间
    cache_ttl_s: int                    # 缓存时间（秒）


class BaseTool(ABC):
    """所有工具必须继承此基类"""
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        ...
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具逻辑"""
        ...
    
    async def invoke(self, agent_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """带网关包装的调用（权限、验证、Trace、审计）"""
        # 1. 权限检查
        if agent_name not in self.definition.permissions:
            raise PermissionError(f"{agent_name} 无权调用 {self.definition.name}")
        
        # 2. 参数验证
        self._validate_params(params)
        
        # 3. 速率限制
        self._check_rate_limit()
        
        # 4. 执行
        start = time.time()
        try:
            result = await asyncio.wait_for(
                self.execute(params),
                timeout=self.definition.timeout_ms / 1000
            )
            result["status"] = "success"
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        
        # 5. 记录
        result["execution_time_ms"] = (time.time() - start) * 1000
        
        return result
```

---

## 4. Data Tools 详细定义

### 4.1 enterprise_query

```json
{
  "name": "enterprise_query",
  "description": "根据企业ID查询企业基础信息",
  "parameters": {
    "type": "object",
    "properties": {
      "enterprise_id": {"type": "string", "description": "企业ID"},
      "fields": {
        "type": "array",
        "items": {"type": "string"},
        "description": "需要返回的字段列表"
      }
    },
    "required": ["enterprise_id"]
  },
  "permissions": ["InvestmentAgent", "RiskAgent", "EnterpriseServiceAgent", "BIAgent"],
  "timeout_ms": 3000
}
```

### 4.2 enterprise_search

```json
{
  "name": "enterprise_search",
  "description": "根据关键词搜索企业",
  "parameters": {
    "type": "object",
    "properties": {
      "keyword": {"type": "string", "description": "搜索关键词"},
      "industry": {"type": "string", "description": "行业筛选"},
      "region": {"type": "string", "description": "区域筛选"},
      "limit": {"type": "integer", "default": 20, "description": "返回数量上限"}
    },
    "required": ["keyword"]
  },
  "permissions": ["InvestmentAgent"],
  "timeout_ms": 5000
}
```

### 4.3 enterprise_profile_get

```json
{
  "name": "enterprise_profile_get",
  "description": "获取企业AI画像（360度全景）",
  "parameters": {
    "type": "object",
    "properties": {
      "enterprise_id": {"type": "string"},
      "include_finance": {"type": "boolean", "default": true},
      "include_technology": {"type": "boolean", "default": true},
      "include_news": {"type": "boolean", "default": true}
    },
    "required": ["enterprise_id"]
  },
  "permissions": ["InvestmentAgent", "RiskAgent", "EnterpriseServiceAgent", "PolicyAgent"],
  "timeout_ms": 5000
}
```

---

## 5. Knowledge Tools 详细定义

### 5.1 policy_vector_search

```json
{
  "name": "policy_vector_search",
  "description": "政策向量语义检索（pgvector）",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "搜索查询（自然语言）"},
      "top_k": {"type": "integer", "default": 5, "description": "返回最相关的K条"},
      "threshold": {"type": "number", "default": 0.7, "description": "相似度阈值"}
    },
    "required": ["query"]
  },
  "permissions": ["PolicyAgent"],
  "timeout_ms": 3000
}
```

### 5.2 policy_metadata_search

```json
{
  "name": "policy_metadata_search",
  "description": "按条件过滤政策（行业、区域、级别等）",
  "parameters": {
    "type": "object",
    "properties": {
      "industry": {"type": "string", "description": "行业，如 robotics"},
      "region": {"type": "string", "description": "区域，如 guangzhou"},
      "level": {"type": "string", "enum": ["national", "provincial", "municipal", "district"]},
      "status": {"type": "string", "enum": ["active", "expired", "upcoming"]}
    },
    "required": []
  },
  "permissions": ["PolicyAgent"],
  "timeout_ms": 2000
}
```

### 5.3 enterprise_vector_search

```json
{
  "name": "enterprise_vector_search",
  "description": "企业语义搜索（pgvector），如"找做机器人视觉的企业"",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "top_k": {"type": "integer", "default": 10}
    },
    "required": ["query"]
  },
  "permissions": ["InvestmentAgent"],
  "timeout_ms": 3000
}
```

---

## 6. Analysis Tools 详细定义

### 6.1 risk_scoring

```json
{
  "name": "risk_scoring",
  "description": "企业风险评分（0-100）",
  "parameters": {
    "type": "object",
    "properties": {
      "enterprise_id": {"type": "string"},
      "include_detail": {"type": "boolean", "default": true}
    },
    "required": ["enterprise_id"]
  },
  "permissions": ["RiskAgent"],
  "timeout_ms": 5000
}
```

**计算公式**：
```
Risk Score = Business Risk ×30% + Finance Risk ×25% + 
             Public Opinion ×15% + Legal ×15% + Talent ×10% + Market ×5%

Level: 0-30 LOW | 31-70 MEDIUM | 71-100 HIGH
```

### 6.2 investment_scoring

```json
{
  "name": "investment_scoring",
  "description": "企业招商价值评分",
  "parameters": {
    "type": "object",
    "properties": {
      "enterprise_id": {"type": "string"}
    },
    "required": ["enterprise_id"]
  },
  "permissions": ["InvestmentAgent"],
  "timeout_ms": 5000
}
```

**计算公式**：
```
Investment Score = 产业匹配度×30% + 成长潜力×25% + 
                   技术能力×20% + 资本能力×15% + 人才价值×10%
```

### 6.3 policy_match_scoring

```json
{
  "name": "policy_match_scoring",
  "description": "企业-政策匹配度评分",
  "parameters": {
    "type": "object",
    "properties": {
      "enterprise_id": {"type": "string"},
      "policy_ids": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["enterprise_id"]
  },
  "permissions": ["PolicyAgent"],
  "timeout_ms": 5000
}
```

---

## 7. Memory Tools 详细定义

### 7.1 memory_save

```json
{
  "name": "memory_save",
  "description": "保存 Agent 记忆",
  "parameters": {
    "type": "object",
    "properties": {
      "agent_name": {"type": "string"},
      "memory_type": {"type": "string", "enum": ["supervisor", "agent", "knowledge"]},
      "content": {"type": "object"},
      "tags": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["agent_name", "memory_type", "content"]
  },
  "permissions": ["Supervisor", "InvestmentAgent", "PolicyAgent", "RiskAgent", "IndustryAgent", "EnterpriseServiceAgent"],
  "timeout_ms": 2000
}
```

### 7.2 memory_search

```json
{
  "name": "memory_search",
  "description": "搜索相关记忆",
  "parameters": {
    "type": "object",
    "properties": {
      "agent_name": {"type": "string"},
      "query": {"type": "string"},
      "memory_type": {"type": "string"},
      "top_k": {"type": "integer", "default": 5}
    },
    "required": ["agent_name", "query"]
  },
  "permissions": ["Supervisor", "InvestmentAgent", "PolicyAgent", "RiskAgent", "IndustryAgent", "EnterpriseServiceAgent"],
  "timeout_ms": 2000
}
```

---

## 8. Agent-Tool 权限矩阵

| Tool | Supervisor | Investment | Policy | Risk | Industry | Service | BI |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| enterprise_query | | ✓ | | ✓ | | ✓ | ✓ |
| enterprise_search | | ✓ | | | | | |
| enterprise_profile_get | | ✓ | ✓ | ✓ | | ✓ | |
| enterprise_vector_search | | ✓ | | | | | |
| policy_query | | | ✓ | | | | ✓ |
| policy_vector_search | | | ✓ | | | | |
| policy_metadata_search | | | ✓ | | | | |
| policy_match_scoring | | | ✓ | | | | |
| industry_query | | | | | ✓ | | ✓ |
| industry_vector_search | | | | | ✓ | | |
| industry_trend_score | | | | | ✓ | | |
| risk_scoring | | | | ✓ | | | |
| knowledge_graph_query | | | | | ✓ | | |
| report_generator | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| memory_save | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| memory_search | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| web_search | | ✓ | | | ✓ | | |
| news_sentiment | | | | ✓ | | | |

---

## 9. Tool 调用流程（含 Trace）

```
Agent 发起调用
  |
  v
Supervisor Tool Gateway
  |
  ├── 1. 权限检查 (agent_name ∈ tool.permissions?)
  ├── 2. 参数验证 (JSON Schema validate)
  ├── 3. 速率限制 (rate_limit check)
  ├── 4. 缓存检查 (cache_ttl_s 内的重复请求直接返回)
  |
  v
[Trace Start] 记录: agent, tool, params, timestamp
  |
  v
Tool.execute(params)
  |
  ├── Database Tool → PostgreSQL/pgvector/Redis
  ├── Knowledge Tool → RAG Pipeline
  ├── Analysis Tool → Scoring Algorithm
  └── External Tool → HTTP API
  |
  v
[Trace End] 记录: result, duration, status
  |
  v
返回 Result + Trace ID
```

---

## 10. 数据库对接

Tool Gateway 通过 Database Agent 访问数据：

```
Tool Gateway
  |
  v
Database Agent (统一数据访问层)
  |
  ├── PostgreSQL  (业务数据)
  ├── pgvector    (向量检索)
  ├── Redis       (缓存 + Memory)
  └── Object Storage (文件/PDF)
```

### 数据库 Tool 到表的映射

| Tool | 表 |
|------|-----|
| enterprise_query | enterprise |
| enterprise_profile_get | enterprise_profile |
| enterprise_search | enterprise + enterprise_profile |
| enterprise_vector_search | enterprise_embedding (pgvector) |
| policy_vector_search | policy_embedding (pgvector) |
| policy_metadata_search | policy |
| risk_scoring | enterprise + risk_indicator + risk_event |
| memory_save | agent_memory |
| memory_search | agent_memory (pgvector) |

---

## 11. 提供给 Supervisor 的 Tool Gateway 接口

```python
# Supervisor 如何暴露 Tool Gateway 给 Agent

class SupervisorToolGateway:
    """Supervisor 内嵌的工具网关"""
    
    async def invoke_tool(
        self,
        agent_name: str,
        tool_name: str,
        params: Dict[str, Any],
        task_id: str
    ) -> ToolResult:
        """
        唯一入口。Agent 调用 tool 时，Supervisor 转发到此方法。
        
        Args:
            agent_name: 调用方 Agent
            tool_name: 工具名称
            params: 工具参数
            task_id: 所属任务 ID
            
        Returns:
            ToolResult: 包含结果和 Trace 信息
        """
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult.error(f"Unknown tool: {tool_name}")
        
        # 完整执行流程
        return await tool.invoke(agent_name, params)
```

---

## 12. 错误处理

```python
class ToolError:
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_PARAMS = "INVALID_PARAMS"
    RATE_LIMITED = "RATE_LIMITED"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    DATABASE_ERROR = "DATABASE_ERROR"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
```

### 降级策略

| 错误类型 | 降级策略 |
|---------|---------|
| DATABASE_ERROR | 尝试缓存数据 → 返回历史数据 + stale 标记 |
| EXECUTION_TIMEOUT | 重试 1 次 → 返回部分结果 |
| RATE_LIMITED | 等待 + 指数退避 |
| UPSTREAM_ERROR | 返回备用数据源 |

---

**文档状态：FROZEN V1.0**
**下一文档：Unified API Contract V1.0**
