# Enterprise Data Tool — Implementation Report V1.0

> **P0 实施完成** | 2026-07-23  
> **分支**: `feature/production-upgrade-v1.2`  
> **基准**: `Enterprise_Data_Tool_Design_V1.0.md`

---

## 1. 实施概览

按照设计文档实现了完整的企业数据工具链：统一 Schema → 适配器 → 核心工具 → Gateway 集成 → API 端点。

### 变更统计

| 类别 | 文件 | 行数 |
|------|------|------|
| 新建 | 8 文件 | ~1,260 |
| 修改 | 5 文件 | ~150 |
| **合计** | **13 文件** | **~1,410** |

### 新建文件

| 文件 | 说明 | 行数 |
|------|------|------|
| `app/schemas/enterprise.py` | EnterpriseProfile / RiskEvent / BusinessStatus / EnterpriseSearchResult | 130 |
| `app/tools/adapters/__init__.py` | 适配器包导出 | 8 |
| `app/tools/adapters/base.py` | DataAdapter 抽象基类 (5 个抽象方法) | 45 |
| `app/tools/adapters/mock.py` | MockAdapter — 迁移 v1.1 所有预设数据 + data_source/confidence/evidence | 280 |
| `app/tools/adapters/tianyancha.py` | TianyanchaAdapter — 天眼查 API (含无 Key 降级) | 85 |
| `app/tools/adapters/qichacha.py` | QichachaAdapter — 企查查 API (含无 Key 降级) | 80 |
| `app/tools/adapters/government.py` | GovernmentAdapter — 政府公示系统 | 55 |
| `app/tools/adapters/factory.py` | create_adapter() 工厂 + 自动降级逻辑 | 60 |
| `app/tools/enterprise_data.py` | EnterpriseDataTool 核心类 (同步+异步双模式) | 210 |

### 修改文件

| 文件 | 改动 | 行数变化 |
|------|------|---------|
| `app/tools/gateway.py` | 替换 5 个 mock → EnterpriseDataTool；新增 2 个工具；扩展权限 | +80 |
| `app/langgraph/nodes/risk_nodes.py` | RiskState 新增 risk_events/business_status；data_request_node 扩展 | +10 |
| `app/api/v1/business.py` | 新增 5 个 API 端点 | +70 |
| `app/config.py` | 新增 6 个配置项 | +8 |
| `.env.example` | 新增企业数据源配置 | +12 |

---

## 2. 新增字段（data_source / source_time / confidence_score / evidence）

所有 Schema 均包含 4 个元数据字段：

```python
data_source: str        # "mock" | "tianyancha" | "qichacha" | "government"
source_time: datetime   # 数据获取时间
confidence_score: float # 0.0–1.0，数据可信度
evidence: List[dict]    # [{type, value, url}] — 数据来源证据链
```

**MockAdapter 示例**:
```json
{
  "enterprise_id": "ENT-001",
  "name": "广东博智林机器人",
  "data_source": "mock",
  "confidence_score": 0.95,
  "source_time": "2026-07-23T10:00:00",
  "evidence": [
    {"type": "preset", "value": "Mock 预设企业: 广东博智林机器人"}
  ]
}
```

---

## 3. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/enterprise/{id}/profile` | 企业完整画像 |
| GET | `/api/v1/enterprise/{id}/risk-events` | 风险事件列表（支持 event_type 筛选） |
| GET | `/api/v1/enterprise/{id}/status` | 经营状态（许可证/处罚/异常） |
| GET | `/api/v1/enterprise/search?query=X` | 企业搜索（支持 industry/location 筛选） |
| GET | `/api/v1/enterprise/data-source` | 当前数据源信息 |

---

## 4. 测试结果

### 4.1 Mock 模式测试（24/24 通过）

| # | 测试项 | 结果 |
|---|--------|------|
| 1 | Schema 导入 | ✅ |
| 2 | Factory 导入 | ✅ |
| 3 | MockAdapter get_profile ENT-001 → 博智林 | ✅ |
| 4 | MockAdapter profile.data_source = "mock" | ✅ |
| 5 | MockAdapter profile.confidence_score > 0 | ✅ |
| 6 | MockAdapter profile.evidence 非空 | ✅ |
| 7 | MockAdapter search "机器人" ≥ 3 结果 | ✅ |
| 8 | MockAdapter risk_events ≥ 2 | ✅ |
| 9 | MockAdapter risk_events 有 evidence | ✅ |
| 10 | MockAdapter business_status = "normal" | ✅ |
| 11 | MockAdapter status.data_source = "mock" | ✅ |
| 12 | MockAdapter 未知企业兜底 | ✅ |
| 13 | MockAdapter scoring > 0 | ✅ |
| 14 | EnterpriseDataTool 单例 | ✅ |
| 15 | EnterpriseDataTool source_name = "mock" | ✅ |
| 16 | Schema Pydantic validation | ✅ |
| 17 | ToolGateway singleton | ✅ |
| 18 | Gateway enterprise_profile_get → success | ✅ |
| 19 | Gateway returns data | ✅ |
| 20 | Gateway enterprise_risk_events → success | ✅ |
| 21 | Gateway enterprise_business_status → success | ✅ |
| 22 | Gateway BIAgent denied risk_events (403) | ✅ |
| 23 | Config enterprise_data_source = "mock" | ✅ |
| 24 | Config has tianyancha_api_key attr | ✅ |

### 4.2 向后兼容测试（19/19 通过）

| # | 测试项 | 结果 |
|---|--------|------|
| 1 | enterprise_search 返回 ≥3 企业 | ✅ |
| 2 | "博智林" 在搜索结果中 | ✅ |
| 3 | enterprise_profile ENT-001 → 广东博智林机器人 | ✅ |
| 4 | profile data_source = "mock" | ✅ |
| 5 | investment_scoring 返回有效分数 | ✅ |
| 6 | policy_vector_search 正常工作 | ✅ |
| 7 | enterprise_risk_events 成功 | ✅ |
| 8 | enterprise_business_status 成功 | ✅ |
| 9 | Risk graph 完整 pipeline → done | ✅ |
| 10 | Risk graph 生成 report | ✅ |
| 11 | Risk graph state 含 risk_events | ✅ |
| 12 | Risk graph state 含 business_status | ✅ |
| 13 | Scoring 确定性（相同入参=相同出参） | ✅ |
| 14-19 | 6 条 API 路由注册 | ✅ |

### 4.3 Real Adapter 模拟测试（无 Key 降级）

| Adapter | 无 Key 行为 | 结果 |
|---------|-----------|------|
| TianyanchaAdapter | 无 Key → factory 自动降级到 MockAdapter + WARNING | ✅ |
| QichachaAdapter | 无 Key → factory 自动降级到 MockAdapter + WARNING | ✅ |
| GovernmentAdapter | 直接返回 fallback（待数据同步方案） | ✅ |
| Factory 降级逻辑 | `create_adapter()` 自动判断 | ✅ |

---

## 5. 架构验证

### 调用链路确认

```
RiskAgent.data_request_node()
  → tg.invoke("enterprise_profile_get")    → ETD.get_profile_sync()     → MockAdapter.get_profile()
  → tg.invoke("enterprise_risk_events")    → ETD.get_risk_events_sync() → MockAdapter.get_risk_events()
  → tg.invoke("enterprise_business_status") → ETD.get_business_status_sync() → MockAdapter.get_business_status()
  
RiskAgent graph pipeline: validate → fetch → features → score → explain → predict → report ✅
```

### 权限矩阵确认

```
RiskAgent: enterprise_query, enterprise_profile_get, risk_scoring, risk_history,
           enterprise_risk_events ✅, enterprise_business_status ✅
BIAgent:   dashboard_query, metric_query (cannot call enterprise_risk_events) ✅
```

---

## 6. 生产切换方式

```bash
# .env
ENTERPRISE_DATA_SOURCE=tianyancha   # 从 mock 切换到天眼查
TIANYANCHA_API_KEY=your_key_here    # 填入真实 API Key
```

- 有 Key: TianyanchaAdapter 正常调用
- 无 Key: factory 自动降级到 MockAdapter + logger.WARNING
- 任意回滚: `ENTERPRISE_DATA_SOURCE=mock` 即恢复 v1.1 行为

---

## 7. 与 v1.1 的差异总结

| 维度 | v1.1 | v1.2 (P0) |
|------|------|-----------|
| 企业数据 | gateway.py 15 个 `_mock_*` 方法 | MockAdapter (迁移所有数据) + 3 个真实 Adapter |
| 数据来源 | 硬编码 | `data_source` 字段标记 |
| 可信度 | 无 | `confidence_score` 0–1 |
| 证据链 | 无 | `evidence: [{type, value, url}]` |
| API 端点 | 0 | 5 个新端点 |
| 切换方式 | 改代码 | 改配置 `ENTERPRISE_DATA_SOURCE` |
| 降级 | 无 | 自动降级 + 告警 |
| 单元测试 | 5 | 43 |
| Mock 行为 | 100% 原样 | 100% 兼容（相同数据，新增字段） |

---

## 8. 已知限制

1. TianyanchaAdapter / QichachaAdapter 的 API 调用代码为 skeleton，需填入真实 API 对接后启用
2. GovernmentAdapter 需数据同步方案（爬虫/离线数据库）
3. EnterpriseDataTool 的同步包装使用 `asyncio.run()`，在高并发场景下可优化为 `run_coroutine_threadsafe`
4. Redis 缓存层未实现（P1 时补充）

---

*Generated by Hermes Agent · 2026-07-23 · Enterprise Data Tool Implementation Report V1.0*
