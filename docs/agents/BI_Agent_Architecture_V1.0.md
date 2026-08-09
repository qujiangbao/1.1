# BI Agent Architecture V1.0

> 版本：V1.0 | Agent：BIAgent（AI数字驾驶舱）
> 状态：READY FOR IMPLEMENTATION

---

## 1. BI Agent 定位

```
BI Agent = AI 数字驾驶舱

不是数据存储，不是业务逻辑。
而是：从各 Agent 消费数据 → 计算指标 → 生成可视化方案 → 输出 Dashboard
```

---

## 2. 工作流

```
Supervisor → TaskMessage
  |
  v
[Query Router]
  |
  ├── kpi_query ────→ [KPI Calculator] ──→ 指标 JSON
  ├── dashboard_data → [Dashboard Builder] → 面板数据
  ├── chart_data ───→ [Chart Generator] ──→ ECharts Option
  └── ai_insight ───→ [Insight Engine] ──→ AI 洞察
  |
  v
[Response Formatter]
  |
  v
TaskResult → Supervisor → Frontend
```

---

## 3. State Schema

```python
class BIState(TypedDict):
    task_id: str
    intent: str                  # kpi_query / dashboard / chart / insight
    
    # 查询参数
    dashboard_type: str          # overview / investment / industry / risk / ai_ops
    chart_id: Optional[str]      # 具体图表
    topic: Optional[str]         # AI 洞察主题
    
    # 数据源（从各 Agent 消费）
    investment_data: Optional[Dict]
    industry_data: Optional[Dict]
    risk_data: Optional[Dict]
    policy_data: Optional[Dict]
    service_data: Optional[Dict]
    agent_runtime_data: Optional[Dict]
    
    # 计算结果
    kpi_result: Optional[Dict]
    dashboard_result: Optional[Dict]
    chart_option: Optional[Dict]  # ECharts Option JSON
    insight_result: Optional[Dict]
    
    status: str
    tools_used: List[str]
    data_sources: List[str]
```

---

## 4. KPI 体系（5 大维度 30+ 指标）

### 4.1 园区运营 KPI

```python
PARK_OVERVIEW_KPI = {
    "total_enterprises": {
        "name": "企业总数",
        "source": "enterprise 表",
        "format": "number",
        "chart": "KPI Card"
    },
    "new_enterprises_mtd": {
        "name": "本月新增",
        "source": "enterprise.created_at",
        "format": "number + trend"
    },
    "growth_rate": {
        "name": "增长率",
        "source": "calculated",
        "format": "percentage"
    },
    "active_rate": {
        "name": "活跃率",
        "source": "enterprise.status",
        "format": "percentage"
    },
    "industry_distribution": {
        "name": "产业分布",
        "source": "enterprise JOIN industry",
        "chart": "Pie Chart"
    },
    "gis_distribution": {
        "name": "GIS 企业分布",
        "source": "enterprise.location",
        "chart": "Geo Map"
    }
}
```

### 4.2 招商 KPI

```python
INVESTMENT_KPI = {
    "opportunity_pool": {
        "name": "目标企业池",
        "source": "InvestmentAgent → enterprise_search result"
    },
    "leads": {"name": "招商线索", "chart": "Number"},
    "in_contact": {"name": "接触中", "chart": "Number"},
    "signed": {"name": "已签约", "chart": "Number"},
    "conversion_rate": {"name": "转化率", "chart": "Funnel"},
    "score_distribution": {"name": "评分分布", "chart": "Bar Chart"},
    "top_enterprises": {"name": "Top 招商企业", "chart": "Ranking List"}
}
```

### 4.3 产业 KPI

```python
INDUSTRY_KPI = {
    "industry_breakdown": {"name": "产业结构", "chart": "TreeMap"},
    "trend_scores": {"name": "趋势评分", "chart": "Radar"},
    "chain_completeness": {"name": "产业链完整度", "chart": "Progress"},
    "growth_hotspots": {"name": "增长热点", "chart": "Heat Map"}
}
```

### 4.4 风险 KPI

```python
RISK_KPI = {
    "risk_distribution": {"name": "风险等级分布", "chart": "Pie"},
    "top_risk_enterprises": {"name": "高风险企业 Top 10", "chart": "Table"},
    "risk_trend": {"name": "风险趋势", "chart": "Line"},
    "risk_by_industry": {"name": "行业风险对比", "chart": "Bar"}
}
```

### 4.5 AI 运营 KPI

```python
AI_OPS_KPI = {
    "agent_calls": {"name": "Agent 调用次数"},
    "task_success_rate": {"name": "任务成功率", "chart": "Gauge"},
    "avg_response_time": {"name": "平均响应时间", "chart": "Line"},
    "token_usage": {"name": "Token 消耗", "chart": "Area"},
    "agent_breakdown": {"name": "各 Agent 调用分布", "chart": "Bar"},
    "error_rate": {"name": "错误率", "chart": "Number"}
}
```

---

## 5. 5 大 Dashboard 数据流

### Dashboard 1: AI园区运营总览

```python
async def overview_dashboard(state: BIState) -> BIState:
    """聚合所有 Agent 的数据生成总览"""
    # 从 Supervisor 获取 Agent Runtime 数据
    agent_data = await get_agent_runtime_stats()
    
    # 从 Database 获取基础统计
    db_data = await tool_gateway.invoke("BIAgent", "dashboard_query", {
        "metrics": ["enterprise_count", "growth_rate", "active_rate"]
    })
    
    state["dashboard_result"] = {
        "cards": [
            {"title": "企业总数", "value": 12580, "trend": "+3.2%"},
            {"title": "招商机会", "value": 230, "trend": "+15%"},
            {"title": "风险企业", "value": 20, "trend": "-5"},
            {"title": "AI任务数", "value": 1520, "trend": "+8%"}
        ],
        "charts": [
            {"type": "line", "title": "企业增长趋势", "data": [...]},
            {"type": "pie", "title": "产业分布", "data": [...]},
            {"type": "map", "title": "企业GIS分布", "data": [...]}
        ]
    }
    return state
```

### Dashboard 2: 招商驾驶舱

```python
# 数据来源：InvestmentAgent
investment_data = await get_investment_stats()
# → 招商漏斗、企业评分排行、招商地图、转化趋势
```

### Dashboard 3: 产业分析驾驶舱

```python
# 数据来源：IndustryAgent
industry_data = await get_industry_stats()
# → 产业链图谱、趋势预测、重点方向
```

### Dashboard 4: 风险驾驶舱

```python
# 数据来源：RiskAgent
risk_data = await get_risk_stats()
# → 风险指数、风险企业列表、风险趋势
```

### Dashboard 5: AI运营中心

```python
# 数据来源：Supervisor Agent
ai_ops_data = await get_agent_runtime_stats()
# → Agent调用、Workflow状态、Task数量、Trace链路
```

---

## 6. ECharts 组件映射

| 数据指标 | ECharts 类型 | 前端组件 |
|---------|-------------|---------|
| 企业总数 | 无（数字卡片） | KPICard |
| 增长率 | Line + Trend | TrendCard |
| 产业分布 | Pie | PieChart |
| 企业增长 | Line | LineChart |
| 招商漏斗 | Funnel | FunnelChart |
| 评分分布 | Bar | BarChart |
| 企业GIS | Scatter (Map) | GeoMap |
| 风险雷达 | Radar | RadarChart |
| 产业链 | Graph | GraphChart |
| 趋势热度 | Heatmap | HeatMap |
| 成功率 | Gauge | GaugeChart |
| AI洞察 | 无（文本卡片） | InsightCard |

---

## 7. AI Insight Engine

```python
async def ai_insight_node(state: BIState) -> BIState:
    """AI 驱动的数据洞察：发现异常、生成建议"""
    topic = state.get("topic", "overview")
    
    # 收集数据
    data = await self._collect_insight_data(topic)
    
    prompt = f"""
你是产业园数据分析师。基于以下数据生成 AI 洞察：

## 数据
{json.dumps(data, ensure_ascii=False)}

请输出 JSON：
{{
  "summary": "一句话洞察",
  "anomalies": [
    {{"metric": "指标名", "value": "异常值", "trend": "上升/下降", "suggestion": "建议"}}
  ],
  "opportunities": [
    {{"area": "领域", "detail": "机会描述", "action": "建议行动"}}
  ],
  "alerts": [
    {{"level": "red/yellow", "message": "预警信息"}}
  ]
}}
"""
    insight = await llm_call(prompt)
    state["insight_result"] = insight
    state["status"] = "done"
    return state
```

---

## 8. Database 需求（BI 数据模型）

```sql
-- BI 指标存储（星型模型）
CREATE TABLE dashboard_metric (
    id SERIAL PRIMARY KEY,
    metric_code VARCHAR(100) UNIQUE,
    metric_name VARCHAR(200),
    metric_category VARCHAR(100),  -- park/investment/industry/risk/ai_ops
    value DOUBLE PRECISION,
    dimension VARCHAR(200),        -- JSON: {"industry": "robot"}
    period VARCHAR(20),            -- daily/weekly/monthly
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Dashboard 组件配置
CREATE TABLE dashboard_widget (
    id SERIAL PRIMARY KEY,
    dashboard_id VARCHAR(50),
    widget_type VARCHAR(50),       -- kpi_card / line_chart / pie_chart ...
    title VARCHAR(200),
    config JSONB,                  -- ECharts option 模板
    position JSONB,                -- {x, y, w, h}
    permission VARCHAR(50)
);
```

---

## 9. API 输出格式

```python
# GET /api/v1/dashboard/overview
{
  "cards": [...],
  "charts": [
    {
      "chart_id": "growth_trend",
      "type": "line",
      "title": "企业增长趋势",
      "option": { ... }  # 完整的 ECharts Option
    }
  ],
  "insights": [...]
}
```

---

## 10. LangGraph 图

```python
def build_bi_graph():
    workflow = StateGraph(BIState)
    
    workflow.add_node("query_router", query_router_node)
    workflow.add_node("kpi_calculator", kpi_calculator_node)
    workflow.add_node("dashboard_builder", dashboard_builder_node)
    workflow.add_node("chart_generator", chart_generator_node)
    workflow.add_node("insight_engine", ai_insight_node)
    workflow.add_node("response_formatter", response_formatter_node)
    
    workflow.set_entry_point("query_router")
    
    workflow.add_conditional_edges("query_router", route_by_intent, {
        "kpi": "kpi_calculator",
        "dashboard": "dashboard_builder",
        "chart": "chart_generator",
        "insight": "insight_engine"
    })
    
    for node in ["kpi_calculator", "dashboard_builder", "chart_generator", "insight_engine"]:
        workflow.add_edge(node, "response_formatter")
    
    workflow.add_edge("response_formatter", END)
    
    return workflow.compile()
```

---

---

## 11. BI 数据契约（V2.0 新增）

各业务 Agent 向 BIAgent 提供数据的标准化格式。

```json
// 示例：InvestmentAgent → BIAgent
{
  "source_agent": "InvestmentAgent",
  "contract_version": "1.0",
  "metrics": [
    {
      "metric_code": "investment_opportunity_pool",
      "metric_name": "目标企业池",
      "value": 230,
      "dimensions": {"industry": "robot"},
      "chart_type": "kpi_card",
      "refresh": "realtime"
    }
  ]
}
```

### 6 Agent 契约汇总

| Agent | 指标数 | 关键指标 |
|-------|:---:|------|
| InvestmentAgent | 6 | 企业池、招商漏斗、评分分布、转化率 |
| PolicyAgent | 4 | 匹配数、通过率、平均匹配度 |
| RiskAgent | 5 | 风险分布、高风险数、趋势、预测预警 |
| IndustryAgent | 5 | 产业热度、完整度、趋势评分 |
| EnterpriseServiceAgent | 4 | 工单数、完成率、响应时间 |
| Supervisor | 5 | Agent调用数、成功率、响应时间、Token消耗 |


**文档状态：V2.0 READY（增加数据契约）**
