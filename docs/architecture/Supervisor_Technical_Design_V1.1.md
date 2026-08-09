# Industrial Park Agent
# Supervisor Agent Technical Implementation Design V1.1

> 版本：V1.1 | 状态：READY FOR IMPLEMENTATION
> 
> 基于 Supervisor Agent Design V1.0，细化到可编码的 LangGraph 节点、State Schema 和路由策略。
> 本文档是 Backend Agent 和所有 Business Agent 的技术实现基线。

---

## 1. Supervisor 定位

```
Supervisor Agent = AI 产业运营总经理

不是业务 Agent。不回答具体问题。
只负责：理解意图 → 规划任务 → 调度 Agent → 聚合结果 → 返回用户
```

---

## 2. LangGraph 整体工作流

```
                    START
                      |
              User Input Node
                      |
             Intent Recognition Node
                      |
              Task Planner Node
                      |
              Agent Router Node
                      |
        ┌─────────────┼─────────────┐
        |             |             |
   IndustryAgent  InvestmentAgent  PolicyAgent  ... (并行或串行)
        |             |             |
        └─────────────┼─────────────┘
                      |
            Result Validator Node
                      |
          Result Aggregator Node
                      |
         Human Approval Node (可选)
                      |
           Final Response Node
                      |
                     END
```

---

## 3. LangGraph State Schema

```python
from typing import TypedDict, List, Optional, Dict, Any, Annotated
from langgraph.graph.message import add_messages
from datetime import datetime

class SupervisorState(TypedDict):
    # === 用户上下文 ===
    user_id: str
    conversation_id: str
    park_id: Optional[str]
    user_role: str                          # admin / manager / viewer
    
    # === 消息流 ===
    messages: Annotated[List[Dict], add_messages]
    user_query: str
    
    # === 意图识别 ===
    intent: Optional[str]                   # 单一意图或 compound
    intents: Optional[List[str]]            # 复合意图时的意图列表
    entities: Optional[Dict[str, Any]]      # 提取的实体
    confidence: Optional[float]             # 意图置信度
    
    # === 任务规划 ===
    task_plan: Optional[List[TaskNode]]     # 任务 DAG
    current_task_index: Optional[int]       # 当前执行到第几个任务
    
    # === Agent 路由 ===
    current_agent: Optional[str]
    agent_input: Optional[Dict[str, Any]]
    agent_results: Dict[str, AgentResult]   # agent_name → result
    
    # === 执行状态 ===
    status: str                             # idle / planning / running / waiting / completed / failed
    error_count: int
    retry_count: int
    
    # === 结果 ===
    aggregated_result: Optional[str]
    final_response: Optional[str]
    
    # === Trace ===
    trace_id: str
    trace_steps: List[TraceStep]
    
    # === 时间 ===
    started_at: str
    completed_at: Optional[str]


class TaskNode(TypedDict):
    task_id: str
    agent: str                             # 目标 Agent 名称
    intent: str                            # 执行意图
    input: Dict[str, Any]                  # 任务输入
    expected_output: List[str]             # 期望输出能力
    dependencies: List[str]                # 依赖的 task_id 列表
    priority: str                          # high / medium / low
    status: str                            # pending / running / completed / failed


class AgentResult(TypedDict):
    task_id: str
    agent: str
    status: str
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    trace: Optional[Dict[str, Any]]
    execution_time_ms: int
    completed_at: str


class TraceStep(TypedDict):
    step: int
    type: str                              # supervisor_decision / agent_call / tool_call
    agent: str
    action: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    timestamp: str
    duration_ms: int
```

---

## 4. Node 详细设计

### 4.1 User Input Node

**职责**：接收并标准化用户输入

```
输入：用户原始消息
处理：
  1. 提取 user_id, conversation_id
  2. 加载历史上下文（最近 10 条消息）
  3. 标准化 query
输出：更新 state.user_query, state.messages
```

### 4.2 Intent Recognition Node

**职责**：识别用户意图并提取实体

```
输入：state.user_query + state.messages (最近上下文)
处理：
  1. LLM 调用：分析意图
  2. 意图分类映射（见 Intent 分类表）
  3. 实体提取（行业、区域、企业名等）
  4. 判断是否为 compound（需要多 Agent 协作）
输出：state.intent, state.intents[], state.entities

提示词关键指令：
  "你是一个产业园 AI 运营官的意图识别器。
   分析用户输入，输出 JSON：
   {
     'intent': '单一意图',
     'intents': ['意图1', '意图2'],  // compound 时
     'entities': {'industry': '...', 'region': '...'},
     'confidence': 0.95,
     'is_compound': false
   }"
```

### 4.3 Task Planner Node

**职责**：将意图转化为可执行的任务 DAG

```
输入：state.intent(s), state.entities
处理：
  1. 根据意图确定需要的 Agent
  2. 分析 Agent 依赖关系
  3. 构建任务 DAG（并行 / 串行 / 条件分支）
  4. 为每个任务生成 TaskNode
输出：state.task_plan

Planner LLM 提示词关键指令：
  "你是任务规划器。根据意图和可用 Agent，生成执行计划。
  可用 Agent：InvestmentAgent, PolicyAgent, IndustryAgent, 
             RiskAgent, EnterpriseServiceAgent, BIAgent
  
  规则：
  - IndustryAgent 必须在 InvestmentAgent 之前（先分析产业再找企业）
  - RiskAgent 和 PolicyAgent 可与 InvestmentAgent 并行
  - EnterpriseServiceAgent 处理服务类请求
  - BIAgent 在所有业务 Agent 之后运行
  
  输出 JSON 任务列表。"
```

### 4.4 Agent Router Node

**职责**：按 DAG 顺序调度 Agent 执行

```
输入：state.task_plan, state.current_task_index
处理：
  1. 获取下一个 pending 且依赖已满足的 TaskNode
  2. 构建 TaskMessage
  3. 通过 Agent Registry 查找 Agent 端点
  4. 发送任务到目标 Agent
  5. 等待结果
  6. 检查状态 → 成功：继续下一个 / 失败：重试或降级
输出：更新 state.current_agent, state.agent_results

任务调度规则：
  - 无依赖关系的任务 → 并行执行
  - 有依赖的任务 → 串行等待
  - 带 priority=high 的任务 → 优先执行
  
Agent 失败处理：
  重试 1（同 Agent） → 重试 2（同 Agent） → Fallback Agent → Human Review
```

### 4.5 Result Validator Node

**职责**：校验 Agent 返回结果

```
输入：state.agent_results[agent_name]
处理：
  1. 检查 status 是否为 success
  2. 验证 result 结构是否包含 expected_output
  3. 检查数据完整性和格式
  4. 评分结果质量（0-1）
输出：验证通过 → 进入 Aggregator / 失败 → 触发重试
```

### 4.6 Result Aggregator Node

**职责**：汇总所有 Agent 结果，生成最终回答

```
输入：state.agent_results (所有完成的结果)
处理：
  1. 按 task_plan 顺序整理结果
  2. 去重和冲突解决
  3. LLM 生成自然语言总结
  4. 附加 Trace 信息
输出：state.aggregated_result, state.final_response

Aggregator Prompt：
  "你是结果汇总器。根据以下 Agent 执行结果，生成面向用户的综合报告。
  保持专业、清晰、有洞察。
  
  Agent 结果：
  - IndustryAgent: {产业分析结果}
  - InvestmentAgent: {招商推荐结果}
  - RiskAgent: {风险评估结果}
  - PolicyAgent: {政策匹配结果}
  
  输出格式：Markdown 报告"
```

### 4.7 Human Approval Node（可选）

**职责**：高风险操作的人工确认

```
触发条件：
  - 批量操作（影响 > 10 条记录）
  - 导出敏感数据
  - 自动化决策（如自动发送招商邀约）
  
处理：
  1. 生成审批摘要
  2. 推送到前端等待确认
  3. 超时 5 分钟自动拒绝
```

### 4.8 Final Response Node

**职责**：格式化并返回最终结果

```
输入：state.final_response, state.trace_steps
输出：
  {
    "conversation_id": "...",
    "response": "最终回答文本",
    "trace_id": "...",
    "agents_used": ["IndustryAgent", "InvestmentAgent"],
    "execution_time_ms": 8500,
    "trace_url": "/agent/trace/{trace_id}"
  }
```

---

## 5. 条件路由逻辑

```python
def router(state: SupervisorState) -> str:
    """决定下一个 Node"""
    
    # 初始路由
    if state["status"] == "idle":
        return "intent_recognition"
    
    # 意图识别完成 → 任务规划
    if state["intent"] and not state["task_plan"]:
        return "task_planner"
    
    # 任务规划完成 → 执行 Agent
    if state["task_plan"] and state["current_task_index"] is None:
        return "agent_router"
    
    # 还有待执行任务
    pending = [t for t in state["task_plan"] 
               if t["status"] == "pending"]
    if pending:
        # 检查依赖是否满足
        ready = [t for t in pending 
                 if all(d in completed_task_ids(state) for d in t["dependencies"])]
        if ready:
            return "agent_router"
    
    # 所有任务完成 → 验证
    if all(t["status"] in ("completed", "failed") 
           for t in state["task_plan"]):
        return "result_validator"
    
    # 验证通过 → 聚合
    if state["status"] == "validated":
        return "result_aggregator"
    
    # 聚合完成 → 输出
    if state["aggregated_result"]:
        return "final_response"
    
    return "end"
```

---

## 6. Agent Registry（Agent 注册表）

Supervisor 通过注册表发现和调用 Agent：

```python
AGENT_REGISTRY = {
    "InvestmentAgent": {
        "name": "InvestmentAgent",
        "display": "AI招商智能体",
        "endpoint": "agent:investment",
        "capabilities": [
            "enterprise_search", "enterprise_profile",
            "enterprise_scoring", "investment_recommend",
            "investment_strategy"
        ],
        "timeout_ms": 30000,
        "retry_count": 2
    },
    "PolicyAgent": {
        "name": "PolicyAgent",
        "display": "AI政策顾问",
        "endpoint": "agent:policy",
        "capabilities": [
            "policy_search", "policy_match",
            "policy_recommend", "policy_analysis"
        ],
        "timeout_ms": 20000,
        "retry_count": 2
    },
    "IndustryAgent": {
        "name": "IndustryAgent",
        "display": "AI产业研究院",
        "endpoint": "agent:industry",
        "capabilities": [
            "industry_chain_analysis", "industry_trend",
            "market_analysis", "investment_direction"
        ],
        "timeout_ms": 25000,
        "retry_count": 2
    },
    "RiskAgent": {
        "name": "RiskAgent",
        "display": "企业风险雷达",
        "endpoint": "agent:risk",
        "capabilities": [
            "risk_score", "risk_analysis",
            "risk_report", "batch_risk_scan", "risk_trend"
        ],
        "timeout_ms": 20000,
        "retry_count": 2
    },
    "EnterpriseServiceAgent": {
        "name": "EnterpriseServiceAgent",
        "display": "AI企业管家",
        "endpoint": "agent:service",
        "capabilities": [
            "service_intent_analysis", "service_classification",
            "ticket_management", "service_workflow"
        ],
        "timeout_ms": 30000,
        "retry_count": 2
    },
    "BIAgent": {
        "name": "BIAgent",
        "display": "AI数字驾驶舱",
        "endpoint": "agent:bi",
        "capabilities": [
            "kpi_query", "dashboard_data",
            "chart_generation", "ai_insight"
        ],
        "timeout_ms": 15000,
        "retry_count": 1
    }
}
```

---

## 7. LangGraph 图构建伪代码

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def build_supervisor_graph() -> StateGraph:
    workflow = StateGraph(SupervisorState)
    
    # 添加节点
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("task_planner", task_planner_node)
    workflow.add_node("agent_router", agent_router_node)
    workflow.add_node("result_validator", result_validator_node)
    workflow.add_node("result_aggregator", result_aggregator_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("final_response", final_response_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # 设置入口
    workflow.set_entry_point("user_input")
    
    # 标准流程
    workflow.add_edge("user_input", "intent_recognition")
    workflow.add_edge("intent_recognition", "task_planner")
    workflow.add_edge("task_planner", "agent_router")
    
    # 条件边：Agent 执行结果
    workflow.add_conditional_edges(
        "agent_router",
        router,
        {
            "agent_router": "agent_router",       # 继续下一个 Agent
            "result_validator": "result_validator",
            "error_handler": "error_handler"
        }
    )
    
    workflow.add_edge("result_validator", "result_aggregator")
    
    # 条件边：是否需要人工审批
    workflow.add_conditional_edges(
        "result_aggregator",
        needs_approval,
        {
            "human_approval": "human_approval",
            "final_response": "final_response"
        }
    )
    
    workflow.add_edge("human_approval", "final_response")
    workflow.add_edge("final_response", END)
    
    # 错误处理后可重试
    workflow.add_edge("error_handler", "agent_router")
    
    # 编译
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app
```

---

## 8. Tool Gateway 接口

Supervisor 通过 Tool Gateway 统一管理所有工具调用：

```python
class ToolGateway:
    """Supervisor 工具网关 - 所有 Agent 调用工具的唯一切入点"""
    
    def __init__(self):
        self.tools = self._load_tools()
    
    def invoke(self, agent_name: str, tool_name: str, params: Dict) -> Dict:
        """
        Agent 调用工具的唯一切入点
        
        流程：
        1. 权限检查：该 Agent 是否有权限调用该 Tool
        2. 参数验证
        3. 执行前 Trace 记录
        4. 调用实际 Tool
        5. 执行后 Trace 记录
        6. 审计日志
        """
        # 1. 权限检查
        if not self._check_permission(agent_name, tool_name):
            return {"error": "PERMISSION_DENIED"}
        
        # 2. 参数验证
        validated = self._validate_params(tool_name, params)
        
        # 3. Trace 记录
        trace_id = self._start_trace(agent_name, tool_name, validated)
        
        # 4. 执行
        result = self._execute(tool_name, validated)
        
        # 5. 完成 Trace
        self._end_trace(trace_id, result)
        
        return result
```

---

## 9. FastAPI 集成接口

Supervisor 通过以下 FastAPI 端点暴露给前端：

```
POST   /api/v1/agent/chat              # 用户对话入口
POST   /api/v1/agent/task              # 创建 Agent 任务
GET    /api/v1/agent/task/{task_id}    # 查询任务状态
GET    /api/v1/agent/task/{task_id}/trace  # 查询执行链路
GET    /api/v1/agent/status            # Agent 整体状态
WS     /api/v1/ws/task/{task_id}       # 实时事件流
```

---

## 10. 标准执行场景

### 场景 1：招商查询（compound 意图）

**用户输入**："帮我找广州的机器人产业链企业，并评估风险"

**Supervisor 执行流程**：
```
Step 1  Intent Recognition  → compound [industry_analysis, investment_search, risk_batch]
Step 2  Task Planner        → 
          Task A: IndustryAgent (产业分析) [无依赖]
          Task B: InvestmentAgent (企业搜索) [依赖: Task A]
          Task C: RiskAgent (批量风险扫描) [依赖: Task B]
Step 3  Agent Router        → 串行执行 A → B → C
Step 4  Result Validator    → 全部 success
Step 5  Result Aggregator   → 生成招商评估报告
Step 6  Final Response      → 返回报告 + Trace
```

### 场景 2：政策查询（单一意图）

**用户输入**："我们公司可以申请什么补贴"

**Supervisor 执行流程**：
```
Step 1  Intent Recognition  → policy_match
Step 2  Task Planner        → Task: PolicyAgent
Step 3  Agent Router        → PolicyAgent
Step 4  Result Validator    → success
Step 5  Result Aggregator   → 格式化政策列表
Step 6  Final Response      → 返回政策推荐
```

---

## 11. 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 意图识别延迟 | < 500ms | LLM 调用 |
| 任务规划延迟 | < 500ms | LLM 调用 |
| 单 Agent 执行 | < 5s | 含数据查询 |
| 复合任务执行 | < 15s | 3-4 个 Agent 协作 |
| Agent 可用率 | > 99% | |
| Trace 完整率 | 100% | 每条任务必须有完整 Trace |

---

## 12. 提供给下游 Agent 的接口契约

每个 Business Agent 必须实现：

```python
class BusinessAgentProtocol:
    """所有业务 Agent 必须实现的接口"""
    
    agent_name: str
    capabilities: List[str]
    
    async def handle_task(self, task: TaskMessage) -> TaskResult:
        """处理 Supervisor 分配的任务"""
        ...
    
    async def health_check(self) -> bool:
        """健康检查"""
        ...
    
    def get_capability_schema(self) -> Dict:
        """返回能力注册信息"""
        ...
```

---

**文档状态：READY FOR IMPLEMENTATION V1.1**
**下一文档：Tool Gateway Design V1.0**
