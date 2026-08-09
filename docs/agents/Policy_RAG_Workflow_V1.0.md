# Policy RAG Agent LangGraph Workflow Design V1.0

> 版本：V1.0 | Agent：PolicyAgent（AI政策顾问）
> 状态：READY FOR IMPLEMENTATION

---

## 1. RAG Pipeline 总览

```
Policy PDFs / Documents
  |
  v
[Phrase 1: Ingestion] 离线/定时
  PDF Parser → Text Extraction → Chunking → Embedding → pgvector
  |
  v
[Phrase 2: Query] 在线/实时
  User Query → Embedding → Vector Search → Top-K Retrieval → Rerank → LLM → Response
```

---

## 2. 实时查询工作流 (LangGraph)

```
Supervisor → TaskMessage
  |
  v
[Query Analyzer] ───────────────────────────
  |                                           |
  v                                           |
[Enterprise Context Loader]                   |
  | (获取企业画像，用于精确匹配)               |
  v                                           |
[Policy Vector Search] ←── pgvector           |
  |                                           |
  v                                           |
[Policy Metadata Filter]                      |
  | (行业/区域/级别过滤)                       |
  v                                           |
[Reranker]                                    |
  | (精排 Top-K)                               |
  v                                           |
[Policy Matcher]                              |
  | (LLM 匹配度评分)                           |
  v                                           |
[Response Formatter]                          |
  |
  v
TaskResult → Supervisor
```

---

## 3. State Schema

```python
class PolicyState(TypedDict):
    # === 任务信息 ===
    task_id: str
    intent: str                     # policy_search / policy_match / policy_recommend
    
    # === 查询输入 ===
    query: str                      # 用户自然语言查询
    enterprise_id: Optional[str]    # 匹配模式下的企业 ID
    
    # === 企业上下文 ===
    enterprise_profile: Optional[Dict]
    enterprise_industry: Optional[str]
    enterprise_region: Optional[str]
    enterprise_scale: Optional[str]
    
    # === 检索中间结果 ===
    raw_chunks: Optional[List[Dict]]        # 向量检索原始结果
    filtered_chunks: Optional[List[Dict]]   # 元数据过滤后
    reranked_chunks: Optional[List[Dict]]   # 精排后
    
    # === 匹配结果 ===
    matched_policies: Optional[List[Dict]]
    # [{policy_id, title, match_score, match_reasons, requirements, materials}]
    
    # === LLM 生成 ===
    llm_response: Optional[str]
    report: Optional[Dict]
    
    # === 控制 ===
    status: str
    error: Optional[Dict]
    retry_count: int
    
    # === Trace ===
    tools_used: List[str]
    data_sources: List[str]
    retrieval_count: int
```

---

## 4. Node 详细设计

### 4.1 Query Analyzer

```python
async def query_analyzer_node(state: PolicyState) -> PolicyState:
    """分析查询意图，提取关键实体"""
    state["query"] = state.get("input", {}).get("query", "")
    state["enterprise_id"] = state.get("input", {}).get("enterprise_id")
    state["intent"] = state.get("input", {}).get("intent", "policy_search")
    
    if state["enterprise_id"]:
        state["status"] = "loading_enterprise"
    else:
        state["status"] = "searching"
    
    state["tools_used"] = []
    state["data_sources"] = []
    state["retrieval_count"] = 0
    
    return state
```

### 4.2 Enterprise Context Loader

```python
async def enterprise_loader_node(state: PolicyState) -> PolicyState:
    """加载企业画像，用于精准策略匹配"""
    if not state.get("enterprise_id"):
        state["status"] = "searching"
        return state
    
    profile = await tool_gateway.invoke(
        "PolicyAgent",
        "enterprise_profile_get",
        {"enterprise_id": state["enterprise_id"]}
    )
    
    state["enterprise_profile"] = profile
    state["enterprise_industry"] = profile.get("industry", "")
    state["enterprise_region"] = profile.get("location", "")
    state["enterprise_scale"] = profile.get("employee_count", "")
    
    state["tools_used"].append("enterprise_profile_get")
    state["data_sources"].append("enterprise_profile")
    state["status"] = "searching"
    
    return state
```

### 4.3 Policy Vector Search

```python
async def vector_search_node(state: PolicyState) -> PolicyState:
    """pgvector 语义检索"""
    # 构建增强查询：企业画像 + 用户查询
    enhanced_query = state["query"]
    if state.get("enterprise_industry"):
        enhanced_query = f"{state['enterprise_industry']}行业 {enhanced_query}"
    
    result = await tool_gateway.invoke(
        "PolicyAgent",
        "policy_vector_search",
        {
            "query": enhanced_query,
            "top_k": 20,
            "threshold": 0.65
        }
    )
    
    state["raw_chunks"] = result.get("chunks", [])
    state["retrieval_count"] = len(state["raw_chunks"])
    state["tools_used"].append("policy_vector_search")
    state["data_sources"].append("policy_embedding")
    state["status"] = "filtering"
    
    return state
```

### 4.4 Policy Metadata Filter

```python
async def metadata_filter_node(state: PolicyState) -> PolicyState:
    """按区域、级别、行业过滤"""
    filters = {}
    if state.get("enterprise_region"):
        region = state["enterprise_region"]
        if "广州" in region:
            filters["region"] = ["guangzhou", "guangdong"]
        elif "广东" in region:
            filters["region"] = ["guangdong"]
    
    if state.get("enterprise_industry"):
        filters["industry"] = state["enterprise_industry"]
    
    # 使用元数据过滤
    result = await tool_gateway.invoke(
        "PolicyAgent",
        "policy_metadata_search",
        filters
    )
    
    # 合并向量检索和过滤结果
    filtered_ids = {p["policy_id"] for p in result.get("policies", [])}
    state["filtered_chunks"] = [
        c for c in state["raw_chunks"]
        if c.get("policy_id") in filtered_ids
    ]
    
    state["tools_used"].append("policy_metadata_search")
    state["data_sources"].append("policy")
    state["status"] = "reranking"
    
    return state
```

### 4.5 Reranker

```python
async def reranker_node(state: PolicyState) -> PolicyState:
    """精排：按相似度 + 时效性 + 级别重排"""
    chunks = state["filtered_chunks"]
    
    # 计算综合分
    for chunk in chunks:
        similarity = chunk.get("similarity", 0)
        level_bonus = {"national": 0.1, "provincial": 0.05, "municipal": 0}.get(
            chunk.get("level", ""), 0
        )
        freshness = min(
            (datetime.now() - chunk.get("publish_date", datetime.min)).days / 365,
            1.0
        )
        chunk["rerank_score"] = similarity * 0.6 + level_bonus + (1 - freshness) * 0.3
    
    chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
    state["reranked_chunks"] = chunks[:10]  # Top 10
    state["status"] = "matching"
    
    return state
```

### 4.6 Policy Matcher

```python
async def policy_matcher_node(state: PolicyState) -> PolicyState:
    """LLM 政策匹配度评分"""
    chunks = state["reranked_chunks"]
    profile = state.get("enterprise_profile", {})
    
    if not profile:
        # 纯搜索模式：直接格式化返回
        state["matched_policies"] = [
            {
                "policy_id": c["policy_id"],
                "title": c["title"],
                "content_snippet": c["content"][:200],
                "level": c.get("level", ""),
                "department": c.get("department", ""),
                "match_score": round(c["rerank_score"] * 100),
            }
            for c in chunks
        ]
        state["status"] = "formatting"
        return state
    
    # 匹配模式：计算精确匹配度
    prompt = f"""
你是政策匹配专家。评估以下政策与企业画像的匹配度。

## 企业画像
行业：{profile.get('industry', '')}
区域：{profile.get('location', '')}
规模：{profile.get('employee_count', '')}人
研发投入：{profile.get('rd_ratio', '')}

## 候选政策
{[f"{c['policy_id']}: {c['title']}\n{c['content'][:300]}" for c in chunks[:5]]}

对每项政策输出 JSON：
[{{
  "policy_id": "...",
  "match_score": 0-100,
  "match_reasons": ["原因1", "原因2"],
  "is_applicable": true/false,
  "application_difficulty": "easy/medium/hard",
  "estimated_subsidy": "金额范围"
}}]
"""
    
    matched = await llm_call(prompt)
    state["matched_policies"] = matched
    state["status"] = "formatting"
    
    return state
```

### 4.7 Response Formatter

```python
async def response_formatter_node(state: PolicyState) -> PolicyState:
    """格式化输出"""
    policies = state["matched_policies"]
    
    state["report"] = {
        "query": state["query"],
        "total_matched": len(policies),
        "policies": policies,
        "trace": {
            "tools_used": state["tools_used"],
            "data_sources": state["data_sources"],
            "retrieval_count": state["retrieval_count"]
        }
    }
    state["status"] = "done"
    
    return state
```

---

## 5. RAG Ingestion Pipeline（离线）

```python
# 政策文档入库流程
class PolicyIngestionPipeline:
    """
    定时/手动触发的政策入库管线
    
    触发：定时任务 / 手动上传
    """
    
    async def ingest(self, pdf_path: str) -> Dict:
        # 1. PDF 解析
        text = await self.parse_pdf(pdf_path)
        
        # 2. 分段
        chunks = self.chunk_text(text, chunk_size=500, overlap=50)
        
        # 3. 元数据提取
        metadata = self.extract_metadata(text)
        
        # 4. Embedding
        embeddings = await self.embed_chunks(chunks)
        
        # 5. 写入 pgvector
        await self.store_chunks(chunks, embeddings, metadata)
        
        return {"status": "success", "chunks": len(chunks)}
```

---

## 6. LangGraph 图定义

```python
def build_policy_graph() -> StateGraph:
    workflow = StateGraph(PolicyState)
    
    workflow.add_node("query_analyzer", query_analyzer_node)
    workflow.add_node("enterprise_loader", enterprise_loader_node)
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("metadata_filter", metadata_filter_node)
    workflow.add_node("reranker", reranker_node)
    workflow.add_node("policy_matcher", policy_matcher_node)
    workflow.add_node("response_formatter", response_formatter_node)
    
    workflow.set_entry_point("query_analyzer")
    
    # 条件：有企业 ID 则先加载企业画像
    workflow.add_conditional_edges(
        "query_analyzer",
        lambda s: "enterprise_loader" if s.get("enterprise_id") else "vector_search",
        {
            "enterprise_loader": "enterprise_loader",
            "vector_search": "vector_search"
        }
    )
    workflow.add_edge("enterprise_loader", "vector_search")
    workflow.add_edge("vector_search", "metadata_filter")
    workflow.add_edge("metadata_filter", "reranker")
    workflow.add_edge("reranker", "policy_matcher")
    workflow.add_edge("policy_matcher", "response_formatter")
    workflow.add_edge("response_formatter", END)
    
    return workflow.compile()
```

---

## 7. 性能指标

| 阶段 | 延迟 | 说明 |
|------|------|------|
| 查询分析 | < 200ms | |
| 企业画像加载 | < 1s | enterprise_profile_get |
| 向量检索 | < 1s | pgvector |
| 元数据过滤 | < 500ms | PostgreSQL |
| 重排序 | < 100ms | 纯计算 |
| LLM 匹配 | < 3s | 5 条政策评分 |
| **总计** | **< 6s** | |

---

## 8. Tool Contract + 完整 API（V2.0 补充）

### 完整 API 列表

```
POST /api/v1/policy/search         # 政策搜索
POST /api/v1/policy/match          # 政策匹配
GET  /api/v1/policy/{id}           # 政策详情 [V2.0新增]
POST /api/v1/policy/ingest         # 政策入库 [V2.0新增]
GET  /api/v1/policy/stats          # 政策统计 [V2.0新增]
GET  /api/v1/policy/categories     # 政策分类树 [V2.0新增]
```

### Tool Contract

```json
{
  "agent": "PolicyAgent",
  "tools_required": [
    "policy_vector_search",
    "policy_metadata_search",
    "policy_document_query",
    "enterprise_profile_get"
  ],
  "output_to": ["Supervisor", "BIAgent", "InvestmentAgent", "EnterpriseServiceAgent"]
}
```


**文档状态：V2.0 READY（补充完整 API）**
