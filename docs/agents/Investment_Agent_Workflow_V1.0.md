# Investment Agent LangGraph Workflow Design V1.0

> 版本：V1.0 | Agent：InvestmentAgent（AI招商智能体）
> 状态：READY FOR IMPLEMENTATION
> 依赖：Agent Communication Contract V1.0, Tool Gateway Design V1.0

---

## 1. 工作流总览

```
Supervisor → TaskMessage
  |
  v
[Intent Parser] ─────────────────────────────
  |                                           |
  v                                           |
[Enterprise Search Node]                      |
  |                                           |
  v                                           |
[Enterprise Profile Node]                     |
  |                                           |
  v                                           |
[Scoring Node]                                |
  |                                           |
  v                                           |
[Recommendation Node]                         |
  |                                           |
  v                                           |
[Strategy Generator]                          |
  |                                           |
  v                                           |
[Report Generator] ────────────────────────────
  |
  v
TaskResult → Supervisor
```

---

## 2. State Schema

```python
from typing import TypedDict, List, Optional, Dict, Any

class InvestmentState(TypedDict):
    # === 任务信息 ===
    task_id: str
    intent: str                             # investment_search / profile / scoring / strategy
    priority: str
    
    # === 输入参数 ===
    query: str                              # 用户查询
    industry: Optional[str]                 # 目标行业
    region: Optional[str]                   # 目标区域
    keywords: Optional[List[str]]           # 搜索关键词
    enterprise_ids: Optional[List[str]]     # 指定企业 ID
    
    # === 执行中间结果 ===
    search_results: Optional[List[Dict]]    # 企业搜索原始结果
    profiles: Optional[List[Dict]]          # 企业画像
    scores: Optional[List[Dict]]            # 评分结果
    recommendations: Optional[List[Dict]]   # 推荐排序
    strategy: Optional[Dict]                # 招商策略
    
    # === 上下文 ===
    industry_context: Optional[Dict]        # 来自 IndustryAgent 的产业背景
    policy_context: Optional[Dict]          # 来自 PolicyAgent 的政策背景
    risk_context: Optional[Dict]            # 来自 RiskAgent 的风险背景
    
    # === 状态控制 ===
    status: str                             # idle / searching / profiling / scoring / done / failed
    error: Optional[Dict]
    retry_count: int
    
    # === Trace ===
    tools_used: List[str]
    data_sources: List[str]

class InvestmentResult(TypedDict):
    task_id: str
    agent: str
    status: str
    result: Dict[str, Any]
    trace: Dict[str, Any]
    execution_time_ms: int
```

---

## 3. Node 设计

### 3.1 Intent Parser Node

```python
async def intent_parser_node(state: InvestmentState) -> InvestmentState:
    """
    解析 Supervisor 传来的任务意图，提取关键参数
    """
    input_data = state.get("input", {})
    
    # 从 TaskMessage 提取参数
    state["intent"] = input_data.get("intent", "investment_search")
    state["query"] = input_data.get("query", "")
    state["industry"] = input_data.get("industry", "")
    state["region"] = input_data.get("region", "guangzhou")
    state["keywords"] = input_data.get("keywords", [])
    
    # 加载产业上下文（如果有）
    if input_data.get("industry_context"):
        state["industry_context"] = input_data["industry_context"]
    
    state["status"] = "searching"
    state["tools_used"] = []
    state["data_sources"] = []
    
    return state
```

### 3.2 Enterprise Search Node

```python
async def enterprise_search_node(state: InvestmentState) -> InvestmentState:
    """
    企业发现：通过 Tool Gateway 搜索目标企业
    """
    # 构建搜索查询
    search_params = {
        "keyword": state["query"],
        "industry": state["industry"],
        "region": state["region"],
        "limit": 20
    }
    
    # 通过 Supervisor Tool Gateway 调用
    result = await tool_gateway.invoke(
        "InvestmentAgent",
        "enterprise_search",
        search_params
    )
    
    state["search_results"] = result.get("enterprises", [])
    state["tools_used"].append("enterprise_search")
    state["data_sources"].append("enterprise")
    
    if state["search_results"]:
        state["enterprise_ids"] = [e["enterprise_id"] for e in state["search_results"]]
        state["status"] = "profiling"
    else:
        state["status"] = "done"
        state["error"] = {"code": "NO_RESULTS", "message": "未找到匹配企业"}
    
    return state
```

### 3.3 Enterprise Profile Node

```python
async def enterprise_profile_node(state: InvestmentState) -> InvestmentState:
    """
    企业画像：为每个候选企业获取 360 度画像
    """
    profiles = []
    
    for eid in state.get("enterprise_ids", []):
        profile = await tool_gateway.invoke(
            "InvestmentAgent",
            "enterprise_profile_get",
            {"enterprise_id": eid}
        )
        profiles.append(profile)
    
    state["profiles"] = profiles
    state["tools_used"].append("enterprise_profile_get")
    state["data_sources"].append("enterprise_profile")
    state["status"] = "scoring"
    
    return state
```

### 3.4 Scoring Node

```python
async def scoring_node(state: InvestmentState) -> InvestmentState:
    """
    企业评分：计算每个企业的招商价值分数
    
    Investment Score = 产业匹配度×30% + 成长潜力×25% + 
                       技术能力×20% + 资本能力×15% + 人才价值×10%
    """
    scores = []
    
    for profile in state.get("profiles", []):
        score = await tool_gateway.invoke(
            "InvestmentAgent",
            "investment_scoring",
            {"enterprise_id": profile["enterprise_id"]}
        )
        scores.append(score)
    
    # 按分数排序
    scores.sort(key=lambda s: s.get("score", 0), reverse=True)
    state["scores"] = scores
    state["tools_used"].append("investment_scoring")
    state["status"] = "recommending"
    
    return state
```

### 3.5 Recommendation Node

```python
async def recommendation_node(state: InvestmentState) -> InvestmentState:
    """
    招商推荐：根据评分生成分级推荐
    """
    scores = state.get("scores", [])
    
    recommendations = []
    for s in scores:
        score = s.get("score", 0)
        
        if score >= 85:
            level = "STRONG_RECOMMEND"
            action = "优先接触"
        elif score >= 70:
            level = "RECOMMEND"
            action = "积极跟进"
        elif score >= 50:
            level = "CONSIDER"
            action = "保持关注"
        else:
            level = "LOW_PRIORITY"
            action = "暂不跟进"
        
        recommendations.append({
            "enterprise_id": s["enterprise_id"],
            "name": s.get("name", ""),
            "score": score,
            "level": level,
            "action": action,
            "match_reasons": s.get("match_reasons", [])
        })
    
    state["recommendations"] = recommendations
    state["status"] = "generating_strategy"
    
    return state
```

### 3.6 Strategy Generator Node

```python
async def strategy_generator_node(state: InvestmentState) -> InvestmentState:
    """
    招商策略：LLM 生成招商策略方案
    
    结合企业画像、评分、产业趋势、政策，生成可执行的招商策略
    """
    recommendations = state.get("recommendations", [])
    industry_ctx = state.get("industry_context", {})
    policy_ctx = state.get("policy_context", {})
    
    strategy_prompt = f"""
你是产业园 AI 招商经理。基于以下信息，生成招商策略：

## 目标产业
{state.get('industry', '')}

## 推荐企业（Top 5）
{recommendations[:5]}

## 产业趋势
{industry_ctx.get('trend', '')}

## 政策环境
{policy_ctx.get('summary', '')}

请输出 JSON 格式：
{{
  "summary": "招商总体策略概述",
  "target_enterprises": [
    {{
      "name": "企业名",
      "approach": "接触方式",
      "value_proposition": "园区价值主张",
      "policy_support": "可提供政策",
      "timeline": "建议时间线"
    }}
  ],
  "industry_strategy": "产业招商策略",
  "risk_notes": "注意事项"
}}
"""
    
    strategy = await llm_call(strategy_prompt)
    state["strategy"] = strategy
    state["status"] = "generating_report"
    
    return state
```

### 3.7 Report Generator Node

```python
async def report_generator_node(state: InvestmentState) -> InvestmentState:
    """
    报告生成：整合所有结果，生成最终招商报告
    """
    report = {
        "task_id": state["task_id"],
        "summary": {
            "total_found": len(state.get("search_results", [])),
            "recommended": len([r for r in state.get("recommendations", []) 
                               if r["level"] in ("STRONG_RECOMMEND", "RECOMMEND")]),
            "avg_score": sum(s.get("score", 0) for s in state.get("scores", [])) / 
                        max(len(state.get("scores", [])), 1)
        },
        "enterprises": state.get("recommendations", []),
        "strategy": state.get("strategy", {}),
        "trace": {
            "tools_used": state.get("tools_used", []),
            "data_sources": state.get("data_sources", [])
        }
    }
    
    state["report"] = report
    state["status"] = "done"
    
    return state
```

---

## 4. LangGraph 图定义

```python
from langgraph.graph import StateGraph, END

def build_investment_graph() -> StateGraph:
    workflow = StateGraph(InvestmentState)
    
    # 添加节点
    workflow.add_node("intent_parser", intent_parser_node)
    workflow.add_node("enterprise_search", enterprise_search_node)
    workflow.add_node("enterprise_profile", enterprise_profile_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("recommendation", recommendation_node)
    workflow.add_node("strategy_generator", strategy_generator_node)
    workflow.add_node("report_generator", report_generator_node)
    workflow.add_node("error_handler", error_handler_node)
    
    workflow.set_entry_point("intent_parser")
    
    # 标准流程
    workflow.add_edge("intent_parser", "enterprise_search")
    workflow.add_conditional_edges(
        "enterprise_search",
        lambda s: "done" if s["status"] == "done" and not s.get("search_results") else "continue",
        {"done": END, "continue": "enterprise_profile"}
    )
    workflow.add_edge("enterprise_profile", "scoring")
    workflow.add_edge("scoring", "recommendation")
    workflow.add_edge("recommendation", "strategy_generator")
    workflow.add_edge("strategy_generator", "report_generator")
    workflow.add_edge("report_generator", END)
    
    return workflow.compile()
```

---

## 5. 依赖和协作

| 依赖方 | 提供内容 | 调用方式 |
|--------|---------|---------|
| Supervisor | TaskMessage（查询参数） | Supervisor → InvestmentAgent |
| DatabaseAgent | 企业数据 | 通过 Tool Gateway |
| IndustryAgent | 产业趋势、招商方向 | Supervisor 在上下文中传入 |
| PolicyAgent | 匹配政策 | Supervisor 在上下文中传入 |
| RiskAgent | 风险评估 | Supervisor 在上下文中传入（可选） |
| BIAgent | 消费招商指标 | InvestmentAgent → Supervisor → BIAgent |

---

## 6. 错误处理

```python
def error_handler_node(state: InvestmentState) -> InvestmentState:
    if state.get("retry_count", 0) < 2:
        state["retry_count"] = state.get("retry_count", 0) + 1
        state["status"] = "searching"  # 从头重试
    else:
        state["status"] = "failed"
        state["error"] = {
            "code": "MAX_RETRY_EXCEEDED",
            "message": "招商分析连续失败",
            "retry_count": state["retry_count"]
        }
    return state
```

---

## 7. 性能指标

| 阶段 | 目标延迟 | 工具调用 |
|------|---------|---------|
| 企业搜索 | < 2s | enterprise_search |
| 企业画像 | < 1s/企业 | enterprise_profile_get |
| 评分计算 | < 500ms/企业 | investment_scoring |
| 策略生成 | < 3s | LLM Call |
| 报告生成 | < 500ms | 无 |
| **总计（10 企业）** | **< 15s** | |

---

**文档状态：READY FOR IMPLEMENTATION**
