# Enterprise Risk Agent LangGraph Workflow Design V1.0

> 版本：V1.0 | Agent：RiskAgent（企业风险预警智能体）
> 状态：READY FOR IMPLEMENTATION

---

## 1. 工作流总览

```
Supervisor → TaskMessage
  |
  v
[Input Validator] ──────────────────────────
  |                                           |
  v                                           |
[Data Request Node] ←── Tool Gateway ──→ enterprise, profile, finance, news...
  |
  v
[Risk Feature Extractor]
  |  提取 6 维风险特征
  v
[Risk Scoring Node]
  |  Risk Score = Σ (factor × weight)
  v
[Risk Explanation Node]
  |  LLM 生成可解释风险报告
  v
[Report Generator]
  |
  v
TaskResult → Supervisor
```

---

## 2. State Schema

```python
class RiskState(TypedDict):
    # === 任务信息 ===
    task_id: str
    intent: str                     # risk_single / risk_batch / risk_trend
    priority: str
    
    # === 输入 ===
    enterprise_id: Optional[str]
    enterprise_ids: Optional[List[str]]  # 批量扫描
    industry: Optional[str]              # 批量扫描时按行业筛选
    
    # === 数据层 ===
    basic_info: Optional[Dict]       # enterprise 表
    profile_data: Optional[Dict]     # enterprise_profile 表
    finance_data: Optional[Dict]     # enterprise_finance 表
    recruitment_data: Optional[Dict] # enterprise_recruitment 表
    news_data: Optional[List[Dict]]  # enterprise_news 表
    legal_data: Optional[List[Dict]] # risk_event 表
    
    # === 特征提取 ===
    risk_features: Optional[Dict]
    # {
    #   "business_risk": 0-100,
    #   "finance_risk": 0-100,
    #   "public_opinion_risk": 0-100,
    #   "legal_risk": 0-100,
    #   "talent_risk": 0-100,
    #   "market_risk": 0-100
    # }
    
    # === 评分 ===
    risk_score: Optional[float]      # 0-100
    risk_level: Optional[str]        # LOW / MEDIUM / HIGH
    
    # === 输出 ===
    explanation: Optional[Dict]      # 风险原因
    recommendation: Optional[str]    # 建议
    report: Optional[Dict]           # 最终报告
    
    # === 批量结果 ===
    batch_results: Optional[List[Dict]]
    
    # === 控制 ===
    status: str
    error: Optional[Dict]
    retry_count: int
    
    # === Trace ===
    tools_used: List[str]
    data_sources: List[str]
```

---

## 3. 风险评分模型

### 3.1 评分公式

```
Risk Score = Business Risk    × 30%
           + Finance Risk     × 25%
           + Public Opinion   × 15%
           + Legal Risk       × 15%
           + Talent Risk      × 10%
           + Market Risk      × 5%
```

### 3.2 等级划分

| Score | Level | 含义 | 建议动作 |
|-------|-------|------|---------|
| 0-30 | LOW | 低风险 | 正常关注 |
| 31-70 | MEDIUM | 中风险 | 月度跟踪 |
| 71-100 | HIGH | 高风险 | 立即走访 |

### 3.3 指标计算逻辑

```python
# Business Risk (经营风险)
# 指标：operation_status, growth_rate, revenue
def calc_business_risk(profile: Dict) -> float:
    risk = 0
    if profile.get("operation_status") == "abnormal":
        risk += 40
    if profile.get("growth_rate", 0) < 0:
        risk += 30  # 负增长
    elif profile.get("growth_rate", 0) < 10:
        risk += 15
    if profile.get("revenue", 0) < 0:
        risk += 30
    return min(risk, 100)

# Finance Risk (财务风险)
def calc_finance_risk(finance: Dict) -> float:
    risk = 0
    if not finance.get("financing_round"):
        risk += 30  # 无融资记录
    if finance.get("cash_flow") == "negative":
        risk += 40
    if finance.get("financing_amount", 0) < 100:
        risk += 30  # 融资额低
    return min(risk, 100)

# Public Opinion Risk (舆情风险)
def calc_opinion_risk(news: List[Dict]) -> float:
    negative = [n for n in news if n.get("sentiment_score", 0) < 0]
    if not negative:
        return 10
    return min(len(negative) * 20, 100)

# Legal Risk (法律风险)
def calc_legal_risk(events: List[Dict]) -> float:
    if not events:
        return 10
    # 按事件严重程度加权
    severity_weight = {"lawsuit": 40, "penalty": 35, "dispute": 25}
    risk = sum(severity_weight.get(e.get("event_type", ""), 15) for e in events)
    return min(risk, 100)

# Talent Risk (人才风险)
def calc_talent_risk(recruitment: Dict) -> float:
    change = recruitment.get("recruitment_change", 0)
    if change < -50:
        return 80  # 大量裁员
    elif change < -20:
        return 50
    elif change < 0:
        return 30
    return 10

# Market Risk (市场风险)
def calc_market_risk(industry_context: Dict = None) -> float:
    if not industry_context:
        return 30
    trend = industry_context.get("trend_score", 50)
    return 100 - trend  # 产业趋势越好，市场风险越低
```

---

## 4. Node 详细设计

### 4.1 Input Validator

```python
async def input_validator_node(state: RiskState) -> RiskState:
    """验证输入参数，确定分析模式"""
    if state.get("enterprise_id"):
        state["intent"] = "risk_single"
    elif state.get("enterprise_ids"):
        state["intent"] = "risk_batch"
    elif state.get("industry"):
        state["intent"] = "risk_batch"
    else:
        state["status"] = "failed"
        state["error"] = {"code": "INVALID_INPUT", "message": "缺少 enterprise_id 或 industry"}
        return state
    
    state["status"] = "fetching_data"
    state["tools_used"] = []
    state["data_sources"] = []
    return state
```

### 4.2 Data Request Node

```python
async def data_request_node(state: RiskState) -> RiskState:
    """通过 Tool Gateway 获取企业多维数据"""
    eid = state["enterprise_id"]
    
    # 并行获取数据
    tasks = [
        tool_gateway.invoke("RiskAgent", "enterprise_query", {"enterprise_id": eid}),
        tool_gateway.invoke("RiskAgent", "enterprise_profile_get", {"enterprise_id": eid}),
        tool_gateway.invoke("RiskAgent", "finance_query", {"enterprise_id": eid}),
        tool_gateway.invoke("RiskAgent", "recruitment_query", {"enterprise_id": eid}),
        tool_gateway.invoke("RiskAgent", "news_query", {"enterprise_id": eid}),
        tool_gateway.invoke("RiskAgent", "legal_query", {"enterprise_id": eid}),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    state["basic_info"] = results[0]
    state["profile_data"] = results[1]
    state["finance_data"] = results[2]
    state["recruitment_data"] = results[3]
    state["news_data"] = results[4] or []
    state["legal_data"] = results[5] or []
    
    state["data_sources"] = [
        "enterprise", "enterprise_profile", "enterprise_finance",
        "enterprise_recruitment", "enterprise_news", "risk_event"
    ]
    state["status"] = "extracting_features"
    
    return state
```

### 4.3 Risk Feature Extractor

```python
async def feature_extractor_node(state: RiskState) -> RiskState:
    """从原始数据提取 6 维风险特征"""
    state["risk_features"] = {
        "business_risk": calc_business_risk(state.get("profile_data", {})),
        "finance_risk": calc_finance_risk(state.get("finance_data", {})),
        "public_opinion_risk": calc_opinion_risk(state.get("news_data", [])),
        "legal_risk": calc_legal_risk(state.get("legal_data", [])),
        "talent_risk": calc_talent_risk(state.get("recruitment_data", {})),
        "market_risk": calc_market_risk(state.get("industry_context"))
    }
    state["status"] = "scoring"
    return state
```

### 4.4 Risk Scoring Node

```python
async def scoring_node(state: RiskState) -> RiskState:
    """加权计算综合风险评分"""
    features = state["risk_features"]
    weights = {
        "business_risk": 0.30,
        "finance_risk": 0.25,
        "public_opinion_risk": 0.15,
        "legal_risk": 0.15,
        "talent_risk": 0.10,
        "market_risk": 0.05
    }
    
    score = sum(features[k] * weights[k] for k in weights)
    score = round(score, 1)
    
    if score <= 30:
        level = "LOW"
    elif score <= 70:
        level = "MEDIUM"
    else:
        level = "HIGH"
    
    state["risk_score"] = score
    state["risk_level"] = level
    state["status"] = "explaining"
    
    return state
```

### 4.5 Risk Explanation Node

```python
async def explanation_node(state: RiskState) -> RiskState:
    """LLM 生成可解释的风险报告"""
    prompt = f"""
你是企业风险分析专家。基于以下数据生成风险报告：

## 企业信息
名称：{state['basic_info'].get('name', '')}
行业：{state['basic_info'].get('industry', '')}

## 风险分析
综合评分：{state['risk_score']}/100（{state['risk_level']}）

## 各维度风险
- 经营风险：{state['risk_features']['business_risk']}/100
- 财务风险：{state['risk_features']['finance_risk']}/100
- 舆情风险：{state['risk_features']['public_opinion_risk']}/100
- 法律风险：{state['risk_features']['legal_risk']}/100
- 人才风险：{state['risk_features']['talent_risk']}/100
- 市场风险：{state['risk_features']['market_risk']}/100

请用中文输出 JSON：
{{
  "summary": "一句话风险概述",
  "risk_factors": [
    {{"type": "维度", "severity": "high/medium/low", "detail": "具体原因"}}
  ],
  "recommendation": "园区应采取的干预建议",
  "alert_level": "green/yellow/red"
}}
"""
    
    explanation = await llm_call(prompt)
    state["explanation"] = explanation
    state["recommendation"] = explanation.get("recommendation", "")
    state["status"] = "generating_report"
    
    return state
```

### 4.6 Report Generator

```python
async def report_generator_node(state: RiskState) -> RiskState:
    """整合生成最终风险报告"""
    state["report"] = {
        "enterprise_id": state["enterprise_id"],
        "enterprise_name": state["basic_info"].get("name", ""),
        "risk_score": state["risk_score"],
        "risk_level": state["risk_level"],
        "risk_factors": state["explanation"].get("risk_factors", []),
        "recommendation": state["recommendation"],
        "alert_level": state["explanation"].get("alert_level", "green"),
        "trace": {
            "tools_used": state["tools_used"],
            "data_sources": state["data_sources"]
        }
    }
    state["status"] = "done"
    return state
```

---

## 5. 批量风险扫描流程

```python
async def batch_risk_scan(enterprise_ids: List[str]) -> List[Dict]:
    """批量风险扫描：对多个企业并行执行风险评估"""
    results = []
    batch_size = 10  # 每批 10 个企业
    
    for i in range(0, len(enterprise_ids), batch_size):
        batch = enterprise_ids[i:i+batch_size]
        tasks = [run_single_risk(eid) for eid in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
    
    # 按风险评分排序（高风险优先）
    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results
```

---

## 6. LangGraph 图定义

```python
def build_risk_graph() -> StateGraph:
    workflow = StateGraph(RiskState)
    
    workflow.add_node("input_validator", input_validator_node)
    workflow.add_node("data_request", data_request_node)
    workflow.add_node("feature_extractor", feature_extractor_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("explanation", explanation_node)
    workflow.add_node("report_generator", report_generator_node)
    workflow.add_node("error_handler", error_handler_node)
    
    workflow.set_entry_point("input_validator")
    
    workflow.add_edge("input_validator", "data_request")
    workflow.add_edge("data_request", "feature_extractor")
    workflow.add_edge("feature_extractor", "scoring")
    workflow.add_edge("scoring", "explanation")
    workflow.add_edge("explanation", "report_generator")
    workflow.add_edge("report_generator", END)
    
    return workflow.compile()
```

---

## 7. 性能指标

| 阶段 | 延迟 | 说明 |
|------|------|------|
| 数据获取 | < 3s | 6 个并行查询 |
| 特征提取 | < 100ms | 纯计算 |
| 评分 | < 10ms | 加权求和 |
| LLM 解释 | < 2s | 风险报告生成 |
| **单企业总计** | **< 6s** | |
| **批量 100 企业** | **< 30s** | 10 并发批处理 |

---

## 8. 提供给 BI Agent 的接口

```
GET /risk/statistics → {
  high: 20,
  medium: 80, 
  low: 500,
  trend: "improving"
}

GET /risk/top_risks → [
  {enterprise_id, name, score, level, reason}
]
```

---

## 9. 预测模型（V2.0 新增）


### 90 天风险预测

```python
class RiskPredictor:
    """
    基于历史 12 个月风险数据，预测未来 90 天走势
    
    输入：过去 12 个月的 6 维风险指标时间序列
    输出：未来 30/60/90 天的预测评分 + 预警信号
    """
    
    async def predict(self, enterprise_id: str) -> Dict:
        history = await self._get_history(enterprise_id, months=12)
        
        # 趋势计算
        trends = {
            dim: self._calc_trend(history, dim)
            for dim in ["business", "finance", "opinion", "legal", "talent", "market"]
        }
        
        # 外推预测
        current = history[-1]["risk_score"]
        slope = sum(trends.values()) / len(trends)
        
        return {
            "current_score": current,
            "predicted_30d": min(100, current + slope * 1),
            "predicted_60d": min(100, current + slope * 2),
            "predicted_90d": min(100, current + slope * 3),
            "direction": "worsening" if slope > 0 else "improving",
            "early_warnings": self._gen_warnings(trends),
        }
```

### 预测 API

```
POST /api/v1/risk/predict
→ {"enterprise_id": "E001"}
← {"current": 45, "predicted_90d": 72, "direction": "worsening",
    "warnings": [{"level": "yellow", "msg": "财务连续恶化"}]}
```


**文档状态：V2.0 READY（增加预测模型）**
