# Industrial Park Agent — ChatGPT 审核后修订文档 V2.0

> 版本：V2.0 | 依据：ChatGPT 最终审核意见
> 变更范围：架构调整 + LLM Gateway + Human Approval + 预测模型 + 数据契约

---

## 一、修订后最终架构

```
                        用户
                         |
                   React Frontend
                   Chat / Dashboard / Trace / GIS
                         |
                   FastAPI Backend
                   API Gateway / WebSocket / JWT / RBAC
                         |
         ┌───────────────┼───────────────┐
         |               |               |
    LLM Gateway     Supervisor      Human Approval
    (模型路由)      (AI运营总经理)    (人工审批)
                         |
        ========================================
        |       |       |       |       |       |
    Industry Investment Policy  Risk   Service  BI
    Agent    Agent     Agent   Agent   Agent   Agent
        |       |       |       |       |       |
        ========================================
                         |
              Supervisor Tool Gateway
         ┌───────┼────────┼────────┐
         |       |        |        |
    Data Tool  RAG Tool  Analysis  External
    (PG/Redis) (pgvector) (评分)   (API)
                         |
        PostgreSQL + pgvector + Redis + Knowledge Base
```

### 关键变化

| 变化 | 原因 |
|------|------|
| **LLM Gateway 独立** | 统一管理模型选择、fallback、Token 计费、速率限制 |
| **Tool Gateway 下移到数据层之上** | Agent 不直接访问数据，Tool Gateway 是唯一数据通道 |
| **Human Approval 前置** | 高风险操作（批量删除、导出敏感数据）必须人工确认 |
| **Knowledge Base 独立** | 政策库/产业报告/企业资料独立于向量库 |

---

## 二、LLM Gateway 设计

### 定位

```
所有 LLM 调用统一经过 LLM Gateway
作用：模型路由、fallback、速率限制、Token 计费、成本控制
```

### 路由策略

```python
class LLMGateway:
    """统一的 LLM 调用入口"""
    
    MODEL_PRIORITY = {
        "reasoning": ["gpt-4o", "claude-sonnet-4", "deepseek-v4"],
        "embedding": ["text-embedding-3-small"],
        "simple":    ["gpt-4o-mini", "deepseek-v4"],
    }
    
    async def invoke(
        self,
        agent_name: str,
        task_type: str,        # reasoning / embedding / simple
        prompt: str,
        max_tokens: int = 2000,
    ) -> LLMResult:
        """
        智能路由 LLM 调用：
        1. 根据 task_type 选择模型优先级
        2. 主模型失败 → 自动 fallback
        3. 记录 token 使用量
        4. 超时 30s 强制降级
        """
        models = self.MODEL_PRIORITY.get(task_type, self.MODEL_PRIORITY["simple"])
        
        for model in models:
            try:
                result = await self._call_model(model, prompt, max_tokens)
                self._log_usage(agent_name, model, result.token_count)
                return result
            except (TimeoutError, RateLimitError) as e:
                logger.warning(f"{model} failed: {e}, trying fallback...")
                continue
        
        raise LLMError("All models exhausted")
    
    def get_usage_report(self) -> Dict:
        """返回各 Agent 的 Token 使用统计"""
        return {
            "by_agent": {...},
            "by_model": {...},
            "total_cost": 0.0,
        }
```

### Fallback 链

```
GPT-4o → Claude Sonnet 4 → DeepSeek V4
  (主)       (备用1)          (备用2)

超时 30s → 自动切换下一个
全部失败 → 返回缓存结果 + stale 标记
```

---

## 三、Human Approval 节点

### 触发条件

| 操作 | 风险等级 | 审批要求 |
|------|:---:|------|
| 批量导出企业数据（>50 条） | HIGH | 必须审批 |
| 自动发送招商邀约 | HIGH | 必须审批 |
| 删除企业记录 | HIGH | 必须审批 |
| 批量风险标记（>100 条） | MEDIUM | 建议审批 |
| 生成对外报告 | MEDIUM | 建议审批 |
| 日常查询 | LOW | 无需审批 |

### 实现

```python
# Supervisor LangGraph 新增节点
def human_approval_node(state: SupervisorState) -> SupervisorState:
    """
    高风险操作暂停，等待人工确认
    
    流程：
    1. 检查 action 风险等级
    2. HIGH → 推送审批请求到前端
    3. 前端展示：操作摘要 + 影响范围 + 确认/拒绝按钮
    4. 超时 5 分钟自动拒绝
    5. 记录审批日志
    """
    action = state.get("pending_action", {})
    if not action:
        return state
    
    # 推送审批到前端
    approval_request = {
        "approval_id": str(uuid4()),
        "task_id": state["task_id"],
        "action": action["type"],
        "summary": action["summary"],
        "impact": action["impact"],
        "requested_by": state["user_id"],
        "timeout_seconds": 300,
    }
    
    # 通过 WebSocket 推送
    await ws_manager.broadcast(
        f"approval:{state['user_id']}",
        {"type": "approval_required", "data": approval_request}
    )
    
    # 等待审批结果（阻塞，或通过回调）
    result = await self._wait_for_approval(approval_request["approval_id"])
    
    if result == "approved":
        state["status"] = "running"
    else:
        state["status"] = "rejected"
        state["final_response"] = "操作已被拒绝（超时或人工拒绝）"
    
    return state
```

### 前端审批 UI

```tsx
// 审批弹窗组件
function ApprovalModal({ request }: { request: ApprovalRequest }) {
  return (
    <Modal title="操作确认" visible>
      <Alert type="warning" message="此操作需要人工审批" />
      <Descriptions>
        <Item label="操作">{request.action}</Item>
        <Item label="影响范围">{request.impact}</Item>
        <Item label="超时时间">5 分钟</Item>
      </Descriptions>
      <Button danger onClick={() => respond("rejected")}>拒绝</Button>
      <Button type="primary" onClick={() => respond("approved")}>确认</Button>
    </Modal>
  );
}
```

---

## 四、Tool Gateway 位置调整

### 旧架构（错误）

```
Agent → Database（直接访问 ❌）
```

### 新架构（正确）

```
Agent → Supervisor → Tool Gateway → Data Tool → Database
                              ↓
                         Trace 记录
                         Audit 日志
```

### 执行链路

```
1. Agent 需要数据
   → 发送 ToolRequest 到 Supervisor

2. Supervisor 转发到 Tool Gateway
   → 权限检查：该 Agent 是否有权调用该 Tool？
   → 参数验证：JSON Schema 校验
   → 速率限制：是否超过配额？

3. Tool Gateway 执行
   → Data Tool → PostgreSQL
   → RAG Tool → pgvector
   → Analysis Tool → 评分计算
   → External Tool → 第三方 API

4. 返回结果 + Trace
   → 记录：谁、何时、调了什么、参数、结果、耗时
```

---

## 五、Risk Agent — 预测模型

### 在现有评分模型基础上增加

```python
class RiskPredictor:
    """
    90 天风险预测模型
    
    输入：历史 12 个月的风险指标时间序列
    输出：未来 90 天的风险走势 + 预警
    """
    
    async def predict(self, enterprise_id: str) -> Dict:
        # 1. 获取历史 12 个月数据
        history = await self._get_risk_history(enterprise_id, months=12)
        
        # 2. 趋势分析
        trends = {
            "business_trend": self._calc_trend(history, "business_risk"),
            "finance_trend": self._calc_trend(history, "finance_risk"),
            "opinion_trend": self._calc_trend(history, "public_opinion_risk"),
        }
        
        # 3. 预测
        prediction = {
            "current_score": history[-1]["risk_score"],
            "predicted_score_30d": self._extrapolate(history, 30),
            "predicted_score_60d": self._extrapolate(history, 60),
            "predicted_score_90d": self._extrapolate(history, 90),
            "risk_direction": "increasing" if trends["business_trend"] > 0 else "stable",
            "early_warnings": self._detect_warnings(trends),
        }
        
        return prediction
    
    def _detect_warnings(self, trends: Dict) -> List[Dict]:
        warnings = []
        if trends["finance_trend"] > 0.5:  # 财务恶化加速
            warnings.append({"level": "red", "message": "财务风险加速恶化，建议立即走访"})
        if trends["opinion_trend"] > 0.3:
            warnings.append({"level": "yellow", "message": "负面舆情增加，关注品牌影响"})
        return warnings
```

### 新增 API

```
POST /api/v1/risk/predict
Request:  {"enterprise_id": "E001"}
Response: {
  "current_score": 45,
  "predicted_score_90d": 72,
  "risk_direction": "increasing",
  "early_warnings": [
    {"level": "yellow", "message": "财务指标连续3月恶化"}
  ]
}
```

---

## 六、BI Agent — 数据契约

### 各 Agent 向 BI 提供的数据格式

```json
{
  "source_agent": "InvestmentAgent",
  "contract_version": "1.0",
  "metrics": [
    {
      "metric_code": "investment_opportunity_pool",
      "metric_name": "目标企业池",
      "value": 230,
      "dimensions": {"industry": "robot", "period": "2026-07"},
      "format": "number",
      "chart_type": "kpi_card",
      "refresh_frequency": "realtime"
    },
    {
      "metric_code": "investment_funnel",
      "metric_name": "招商转化漏斗",
      "value": {"discovered": 230, "contacted": 45, "negotiating": 20, "signed": 12},
      "format": "funnel",
      "chart_type": "funnel_chart",
      "refresh_frequency": "daily"
    }
  ]
}
```

### 6 个业务 Agent 的 BI 契约

| Agent | 提供指标数 | 关键指标 |
|-------|:---:|------|
| InvestmentAgent | 6 | 目标企业池、招商漏斗、评分分布、转化率 |
| PolicyAgent | 4 | 政策匹配数、申请通过率、平均匹配度 |
| RiskAgent | 5 | 风险分布、高风险企业数、风险趋势、预测预警 |
| IndustryAgent | 5 | 产业热度、产业链完整度、趋势评分 |
| EnterpriseServiceAgent | 4 | 工单数、完成率、响应时间、满意度 |
| Supervisor | 5 | Agent 调用次数、成功率、响应时间、Token 消耗 |

---

## 七、Policy Agent — API Contract 补充

### 完整 API 列表

```
POST /api/v1/policy/search        # 政策搜索（已定义）
POST /api/v1/policy/match         # 政策匹配（已定义）
GET  /api/v1/policy/{id}          # 政策详情 [新增]
POST /api/v1/policy/ingest        # 政策入库 [新增]
GET  /api/v1/policy/stats         # 政策统计 [新增]
GET  /api/v1/policy/categories    # 政策分类树 [新增]
```

---

## 八、Demo — 稳定数据层

```python
# demo_data_layer.py
"""
Demo 稳定数据层：确保比赛现场即使 LLM 不稳定也能跑通 Demo

策略：核心数据预加载，LLM 仅用于意图识别和报告润色
"""

DEMO_DATA = {
    # 预置产业分析结果
    "industry_robot": {
        "trend_score": 85,
        "trend_level": "STRATEGIC",
        "chain": {
            "upstream": ["传感器", "伺服电机", "控制器", "减速器"],
            "midstream": ["工业机器人", "服务机器人", "协作机器人"],
            "downstream": ["汽车制造", "3C电子", "医疗", "物流"]
        },
        "market_size": "5000亿",
        "growth_rate": "25%",
    },
    
    # 预置企业数据（Top 5）
    "enterprises": [
        {"id": "E001", "name": "广州智行机器人", "industry": "工业机器人",
         "score": 92, "level": "STRONG_RECOMMEND", "city": "广州黄埔"},
        {"id": "E002", "name": "拓斯达科技", "industry": "工业机器人",
         "score": 88, "level": "RECOMMEND", "city": "东莞"},
        {"id": "E003", "name": "优必选科技", "industry": "服务机器人",
         "score": 85, "level": "RECOMMEND", "city": "深圳"},
        {"id": "E004", "name": "广州数控", "industry": "数控系统",
         "score": 82, "level": "RECOMMEND", "city": "广州"},
        {"id": "E005", "name": "伯朗特智能", "industry": "工业机器人",
         "score": 78, "level": "CONSIDER", "city": "东莞"},
    ],
    
    # 预置风险评分
    "risk_scores": {
        "E001": {"score": 28, "level": "LOW"},
        "E002": {"score": 35, "level": "MEDIUM"},
        "E003": {"score": 22, "level": "LOW"},
        "E004": {"score": 45, "level": "MEDIUM"},
        "E005": {"score": 55, "level": "MEDIUM"},
    },
    
    # 预置政策匹配
    "policy_matches": {
        "E001": [
            {"title": "广州市人工智能产业扶持办法", "score": 95},
            {"title": "黄埔区机器人产业专项政策", "score": 90},
        ]
    }
}

# Demo 模式：优先使用预置数据，LLM 仅做意图识别
async def demo_chat(message: str) -> Dict:
    intent = await llm_gateway.invoke("Supervisor", "simple", 
        f"识别意图: {message}", max_tokens=50)
    
    if "机器人" in message:
        return build_demo_response("robot")
    elif "政策" in message:
        return build_demo_response("policy")
    else:
        return build_demo_response("robot")  # 默认
```

---

## 九、修改后的开发顺序

```
Phase 1: Engineering Freeze ✅ (已完成)
  ├── Agent Communication Contract V1.0 ✅
  ├── Supervisor Technical Design V1.1 ✅
  ├── Tool Gateway Design V1.0 ✅
  ├── Unified API Contract V1.0 ✅
  ├── LLM Gateway Design ✅ (本次新增)
  └── Human Approval Design ✅ (本次新增)

Phase 2: Backend 代码实现（当前）
  ├── FastAPI 项目骨架 ✅
  ├── LLM Gateway 实现
  ├── Human Approval 实现
  ├── 6 个 Business Agent Node 实现
  └── Tool Gateway 实现

Phase 3: Frontend 页面开发
  ├── AI Chat + Agent 动画
  ├── Agent Trace 可视化 (React Flow)
  ├── Dashboard 驾驶舱
  └── Human Approval UI

Phase 4: Demo 打磨
  ├── Demo 数据层
  ├── 5 分钟演示彩排
  └── PPT + 路演脚本
```

---

## 十、架构完整性自检

| 检查项 | 状态 |
|--------|:---:|
| Agent Communication Contract 冻结 | ✅ |
| API Contract 冻结 | ✅ |
| Tool Gateway 位置修正 | ✅ |
| LLM Gateway 新增 | ✅ |
| Human Approval 新增 | ✅ |
| Agent 运行数据表确认 | ✅ |
| Risk 预测模型 | ✅ |
| BI 数据契约 | ✅ |
| Demo 稳定数据层 | ✅ |

---

**文档状态：V2.0 FINAL**
**项目已具备进入编码阶段的所有条件。**
