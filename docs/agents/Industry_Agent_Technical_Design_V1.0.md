# Industry Intelligence Agent Technical Design V1.0

> 版本：V1.0 | Agent：IndustryAgent（AI产业研究院）
> 状态：READY FOR IMPLEMENTATION

---

## 1. 工作流总览

```
Supervisor → TaskMessage
  |
  v
[Intent Parser]
  |
  ├── industry_chain_analysis  → [Chain Analyzer]  → 产业链结构 + 缺口
  ├── industry_trend           → [Trend Predictor]  → 趋势评分 + 预测
  ├── market_analysis          → [Market Analyzer]  → TAM/SAM/SOM
  └── investment_direction     → [Direction Advisor] → 招商方向推荐
  |
  v
[Report Generator]
  |
  v
TaskResult → Supervisor
```

---

## 2. State Schema

```python
class IndustryState(TypedDict):
    task_id: str
    intent: str              # chain_analysis / trend / market / direction
    industry: str
    region: Optional[str]
    
    # 分析结果
    chain_result: Optional[Dict]      # 产业链数据
    trend_score: Optional[float]      # 0-100
    market_result: Optional[Dict]     # 市场分析
    direction_result: Optional[List]  # 招商方向
    
    # RAG 相关
    retrieved_docs: Optional[List]
    knowledge_graph: Optional[Dict]
    
    report: Optional[Dict]
    status: str
    
    tools_used: List[str]
    data_sources: List[str]
```

---

## 3. Node 详细设计

### 3.1 Intent Parser

```python
async def intent_parser_node(state: IndustryState) -> IndustryState:
    state["industry"] = state.get("input", {}).get("industry", "")
    state["region"] = state.get("input", {}).get("region", "guangzhou")
    state["intent"] = state.get("input", {}).get("intent", "industry_analysis")
    state["tools_used"] = []
    state["data_sources"] = []
    state["status"] = "analyzing"
    return state
```

### 3.2 Chain Analyzer（产业链分析）

```python
async def chain_analyzer_node(state: IndustryState) -> IndustryState:
    """分析产业链结构、识别缺口"""
    # 1. RAG 检索产业知识
    docs = await tool_gateway.invoke(
        "IndustryAgent", "industry_vector_search",
        {"query": f"{state['industry']} 产业链 上下游"}
    )
    
    # 2. 知识图谱查询
    kg = await tool_gateway.invoke(
        "IndustryAgent", "knowledge_graph_query",
        {"industry": state["industry"]}
    )
    
    # 3. 企业数据统计
    companies = await tool_gateway.invoke(
        "IndustryAgent", "industry_query",
        {"industry": state["industry"], "region": state["region"]}
    )
    
    state["chain_result"] = {
        "upstream": kg.get("upstream", []),
        "midstream": kg.get("midstream", []),
        "downstream": kg.get("downstream", []),
        "enterprise_count": companies.get("total", 0),
        "gaps": self._identify_gaps(kg, companies),
        "completeness": self._calc_completeness(kg, companies)
    }
    
    state["tools_used"].extend(["industry_vector_search", "knowledge_graph_query", "industry_query"])
    state["data_sources"].extend(["industry_embedding", "knowledge_graph", "industry"])
    state["status"] = "trend_analysis"
    
    return state
```

### 3.3 Trend Predictor（趋势预测）

```python
async def trend_predictor_node(state: IndustryState) -> IndustryState:
    """多维趋势评分"""
    indicators = await tool_gateway.invoke(
        "IndustryAgent", "industry_trend_score",
        {"industry": state["industry"]}
    )
    
    # Industry Trend Score = 
    #   Market Growth ×30% + Tech Momentum ×25% + 
    #   Capital Activity ×20% + Policy Support ×15% + Talent Growth ×10%
    
    weights = {"market_growth": 0.30, "tech_momentum": 0.25, 
               "capital_activity": 0.20, "policy_support": 0.15, "talent_growth": 0.10}
    
    score = sum(indicators[k] * weights[k] for k in weights)
    state["trend_score"] = round(score, 1)
    
    level = "STRATEGIC" if score >= 90 else ("FOCUS" if score >= 70 else "WATCH")
    state["trend_level"] = level
    
    state["status"] = "done"
    return state
```

### 3.4 Market Analyzer（市场分析）

```python
async def market_analyzer_node(state: IndustryState) -> IndustryState:
    """TAM-SAM-SOM 分析"""
    state["market_result"] = {
        "tam": await self._estimate_tam(state["industry"]),
        "growth_rate": "25%",
        "competition_landscape": "中等集中",
        "guangzhou_position": "系统集成优势明显，高端零部件依赖进口",
        "opportunities": ["核心零部件国产替代", "AI+机器人融合", "服务机器人增长"]
    }
    return state
```

### 3.5 Direction Advisor（招商方向）

```python
async def direction_advisor_node(state: IndustryState) -> IndustryState:
    """生成招商方向推荐"""
    chain = state.get("chain_result", {})
    gaps = chain.get("gaps", [])
    
    directions = []
    for gap in gaps:
        directions.append({
            "direction": gap["name"],
            "priority": "HIGH" if gap["severity"] == "critical" else "MEDIUM",
            "reason": f"产业链缺口：{gap['description']}",
            "target_type": gap.get("target_type", "technology_company")
        })
    
    state["direction_result"] = directions
    state["status"] = "generating_report"
    return state
```

---

## 4. 知识图谱模型

```
Industry ——[has_chain]——> ChainNode (upstream/midstream/downstream)
Company ——[belongs_to]——> Industry
Company ——[develops]——> Technology
Company ——[supplies]——> Company
Industry ——[supported_by]——> Policy
Industry ——[located_in]——> Region
```

---

## 5. LangGraph 图

```python
def build_industry_graph():
    workflow = StateGraph(IndustryState)
    
    workflow.add_node("intent_parser", intent_parser_node)
    workflow.add_node("chain_analyzer", chain_analyzer_node)
    workflow.add_node("trend_predictor", trend_predictor_node)
    workflow.add_node("market_analyzer", market_analyzer_node)
    workflow.add_node("direction_advisor", direction_advisor_node)
    workflow.add_node("report_generator", report_generator_node)
    
    workflow.set_entry_point("intent_parser")
    workflow.add_edge("intent_parser", "chain_analyzer")
    workflow.add_edge("chain_analyzer", "trend_predictor")
    workflow.add_edge("trend_predictor", "market_analyzer")
    workflow.add_edge("market_analyzer", "direction_advisor")
    workflow.add_edge("direction_advisor", "report_generator")
    workflow.add_edge("report_generator", END)
    
    return workflow.compile()
```

---

## 6. 性能指标

| 阶段 | 延迟 |
|------|------|
| 产业链分析 | < 3s |
| 趋势评分 | < 1s |
| 市场分析 | < 2s (LLM) |
| 招商方向 | < 2s (LLM) |
| **总计** | **< 10s** |

---

**文档状态：READY FOR IMPLEMENTATION**
