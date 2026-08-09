# Enterprise Service Agent Architecture V1.0

> 版本：V1.0 | Agent：EnterpriseServiceAgent（AI企业管家）
> 状态：READY FOR IMPLEMENTATION

---

## 1. 工作流总览

```
Supervisor → TaskMessage
  |
  v
[Intent Analyzer] ─ 识别企业需求类型
  |
  v
[Service Classifier] ─ 分类到 8 大服务体系
  |
  ├── Policy Service → [Supervisor → PolicyAgent]
  ├── Talent Service → [Supervisor → 外部]
  ├── Finance Service → [Supervisor → 外部]
  ├── Technology Service → [Supervisor → IndustryAgent]
  ├── Market Service → [Supervisor → IndustryAgent]
  ├── Space Service → [工单系统]
  ├── Government Service → [Supervisor → PolicyAgent]
  └── Growth Service → [综合]
  |
  v
[Ticket Manager] ─ 创建/更新服务工单
  |
  v
[Workflow Engine] ─ 自动化服务流程
  |
  v
[Result Aggregator] ─ 汇总结果
  |
  v
TaskResult → Supervisor
```

---

## 2. State Schema

```python
class ServiceState(TypedDict):
    task_id: str
    enterprise_id: str
    
    # 输入
    request: str                    # 企业需求描述
    priority: str                   # high/medium/low
    
    # 分析
    intent: str                     # 需求意图类型
    service_category: str           # 8 大分类
    sub_services: List[str]         # 需要调用的子服务
    
    # 工单
    ticket_id: Optional[str]
    ticket_status: str              # created/processing/waiting/completed
    
    # 生命周期
    lifecycle_stage: str            # 注册/入园/成长/扩张/成熟
    
    # 结果
    agent_results: Dict[str, Dict]  # 各子 Agent 结果
    final_response: Optional[Dict]
    
    # 控制
    status: str
    tools_used: List[str]
    data_sources: List[str]
```

---

## 3. 8 大服务体系

```python
SERVICE_CATALOG = {
    "policy_service": {
        "name": "政策服务",
        "agent": "PolicyAgent",
        "actions": ["政策查询", "补贴申请", "资质认定"]
    },
    "talent_service": {
        "name": "人才服务",
        "actions": ["人才招聘", "人才政策", "培训对接"]
    },
    "finance_service": {
        "name": "金融服务",
        "actions": ["融资对接", "贷款咨询", "上市辅导"]
    },
    "technology_service": {
        "name": "技术服务",
        "agent": "IndustryAgent",
        "actions": ["技术对接", "产学研", "检测认证"]
    },
    "market_service": {
        "name": "市场服务",
        "agent": "IndustryAgent",
        "actions": ["产业链对接", "市场拓展", "品牌推广"]
    },
    "space_service": {
        "name": "空间服务",
        "actions": ["办公空间", "厂房需求", "实验室"]
    },
    "government_service": {
        "name": "政务服务",
        "agent": "PolicyAgent",
        "actions": ["工商变更", "税务咨询", "行政审批"]
    },
    "growth_service": {
        "name": "成长服务",
        "actions": ["战略咨询", "管理培训", "上市规划"]
    }
}
```

---

## 4. Node 设计

### 4.1 Intent Analyzer

```python
async def intent_analyzer_node(state: ServiceState) -> ServiceState:
    """LLM 分析企业需求，输出意图和服务分类"""
    prompt = f"""
你是企业服务意图识别器。分析以下需求：

企业需求：{state['request']}

从以下分类中选择最匹配的：
{list(SERVICE_CATALOG.keys())}

输出 JSON：
{{
  "primary_intent": "主要意图",
  "service_category": "主分类",
  "sub_services": ["子服务1", "子服务2"],
  "lifecycle_stage": "注册/入园/成长/扩张/成熟",
  "urgency": "urgent/normal/low",
  "requires_agent": ["PolicyAgent", "IndustryAgent"] 或 []
}}
"""
    analysis = await llm_call(prompt)
    state["intent"] = analysis["primary_intent"]
    state["service_category"] = analysis["service_category"]
    state["sub_services"] = analysis["sub_services"]
    state["lifecycle_stage"] = analysis["lifecycle_stage"]
    state["status"] = "creating_ticket"
    return state
```

### 4.2 Ticket Manager

```python
async def ticket_manager_node(state: ServiceState) -> ServiceState:
    """创建服务工单"""
    ticket = {
        "ticket_id": f"ST-{state['task_id']}",
        "enterprise_id": state["enterprise_id"],
        "service_category": state["service_category"],
        "sub_services": state["sub_services"],
        "priority": state["priority"],
        "status": "processing",
        "created_at": datetime.now().isoformat()
    }
    
    state["ticket_id"] = ticket["ticket_id"]
    state["ticket_status"] = "processing"
    state["status"] = "routing"
    
    return state
```

### 4.3 Workflow Engine

```python
async def workflow_engine_node(state: ServiceState) -> ServiceState:
    """根据服务分类，通过 Supervisor 调用对应 Agent"""
    sub_services = state["sub_services"]
    results = {}
    
    for service in sub_services:
        catalog = SERVICE_CATALOG.get(service, {})
        agent = catalog.get("agent")
        
        if agent:
            # 通过 Supervisor 调用
            task_msg = {
                "task_id": f"{state['task_id']}-{service}",
                "to_agent": agent,
                "intent": service,
                "input": {
                    "enterprise_id": state["enterprise_id"],
                    "requirement": state["request"]
                }
            }
            result = await supervisor_dispatch(task_msg)
            results[service] = result
    
    state["agent_results"] = results
    state["status"] = "aggregating"
    return state
```

### 4.4 Result Aggregator

```python
async def result_aggregator_node(state: ServiceState) -> ServiceState:
    """汇总所有子服务结果"""
    state["final_response"] = {
        "ticket_id": state["ticket_id"],
        "enterprise_id": state["enterprise_id"],
        "service_category": state["service_category"],
        "lifecycle_stage": state["lifecycle_stage"],
        "results": state["agent_results"],
        "summary": f"已完成 {len(state['agent_results'])} 项服务处理",
        "next_steps": self._suggest_next_steps(state)
    }
    state["status"] = "done"
    return state
```

---

## 5. 企业生命周期管理

```python
LIFECYCLE_STAGES = {
    "registered": {
        "name": "注册",
        "services": ["government_service", "space_service"],
        "checklist": ["工商注册", "税务登记", "办公空间"]
    },
    "onboarding": {
        "name": "入园", 
        "services": ["policy_service", "space_service"],
        "checklist": ["入园手续", "政策宣讲", "资源对接"]
    },
    "growing": {
        "name": "成长",
        "services": ["talent_service", "finance_service", "technology_service"],
        "checklist": ["人才招聘", "融资对接", "技术合作"]
    },
    "expanding": {
        "name": "扩张",
        "services": ["market_service", "finance_service", "growth_service"],
        "checklist": ["市场拓展", "规模融资", "品牌提升"]
    },
    "mature": {
        "name": "成熟",
        "services": ["growth_service", "market_service"],
        "checklist": ["上市规划", "产业贡献", "生态建设"]
    }
}
```

---

## 6. LangGraph 图

```python
def build_service_graph():
    workflow = StateGraph(ServiceState)
    
    workflow.add_node("intent_analyzer", intent_analyzer_node)
    workflow.add_node("ticket_manager", ticket_manager_node)
    workflow.add_node("workflow_engine", workflow_engine_node)
    workflow.add_node("result_aggregator", result_aggregator_node)
    
    workflow.set_entry_point("intent_analyzer")
    workflow.add_edge("intent_analyzer", "ticket_manager")
    workflow.add_edge("ticket_manager", "workflow_engine")
    workflow.add_edge("workflow_engine", "result_aggregator")
    workflow.add_edge("result_aggregator", END)
    
    return workflow.compile()
```

---

## 7. 数据库需求

提交给 Database Agent 的新增表：

```sql
-- 服务请求
CREATE TABLE enterprise_service_request (
    id SERIAL PRIMARY KEY,
    enterprise_id VARCHAR(50) NOT NULL,
    request_text TEXT,
    intent VARCHAR(100),
    service_category VARCHAR(100),
    priority VARCHAR(20),
    lifecycle_stage VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 服务工单
CREATE TABLE service_ticket (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(50) UNIQUE NOT NULL,
    enterprise_id VARCHAR(50) NOT NULL,
    service_category VARCHAR(100),
    status VARCHAR(30),
    assigned_agents JSONB,
    results JSONB,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- 服务历史
CREATE TABLE service_history (
    id SERIAL PRIMARY KEY,
    enterprise_id VARCHAR(50),
    service_type VARCHAR(100),
    description TEXT,
    result JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 企业服务记忆
CREATE TABLE enterprise_service_memory (
    id SERIAL PRIMARY KEY,
    enterprise_id VARCHAR(50),
    memory_type VARCHAR(50),
    content JSONB,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

**文档状态：READY FOR IMPLEMENTATION**
