# Policy RAG — Technical Design Review V1.0

> **P1 实现级设计评审** — 对接现有 PolicyAgent，不改 Agent 职责  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-23

---

## 1. 现有 PolicyAgent 审计 & 对接方案

### 1.1 现有 6 节点 Pipeline（不改）

```
query_analyzer → enterprise_loader → vector_search → metadata_filter → policy_matcher → response_formatter
```

每个节点的**输入/输出接口不变**，只替换节点内部的数据获取方式。

### 1.2 节点级改动映射

```
节点                 当前实现                          P1 改动
──────────────────────────────────────────────────────────────────
query_analyzer      解析 input → query, eid           ✅ 不变
enterprise_loader   调用 enterprise_profile_get        ✅ 不变（P0 已对接）
vector_search ⚡     调用 policy_vector_search(mock)    ⚡ → policy_hybrid_search(KnowledgeTool)
metadata_filter ⚡   调用 policy_metadata_search(mock)   ⚡ → 内存过滤（基于 hybrid_search 结果）
policy_matcher      相似度排序 + 去重                  ✅ 逻辑不变，输入格式不变
response_formatter  组装 report                        ✅ 不变
```

### 1.3 PolicyState（新增 1 字段）

```python
class PolicyState(TypedDict):
    # ... 现有字段不变 ...
    raw_chunks: Optional[List[Dict]]         # 保留
    filtered_chunks: Optional[List[Dict]]    # 保留
    matched_policies: Optional[List[Dict]]   # 保留
    report: Optional[Dict]                   # 保留
    # ⚡ 新增
    search_mode: Optional[str]               # "mock" | "pgvector"
```

### 1.4 vector_search_node 改动（核心）

```python
# 改前: 调用 mock
def vector_search_node(state):
    r = tg.invoke("PolicyAgent", "policy_vector_search", {"query": q, "top_k": 10})
    state["raw_chunks"] = r.data.get("chunks", [])
    ...

# 改后: 调用 KnowledgeTool
def vector_search_node(state):
    r = tg.invoke("PolicyAgent", "policy_hybrid_search", {
        "query": q,
        "top_k": 10,
        "filters": {
            "level": state.get("input", {}).get("level"),
            "region": (state.get("enterprise_profile") or {}).get("location"),
            "industry": (state.get("enterprise_profile") or {}).get("industry"),
        }
    })
    state["raw_chunks"] = r.data.get("chunks", [])
    state["search_mode"] = r.data.get("mode", "mock")
    ...
```

### 1.5 metadata_filter_node 改动

```python
# 改前: 再调一次 ToolGateway
def metadata_filter_node(state):
    r = tg.invoke("PolicyAgent", "policy_metadata_search", {...})
    ...

# 改后: 内存过滤（hybrid_search 已包含过滤）
def metadata_filter_node(state):
    chunks = state.get("raw_chunks", [])
    # 本地排序 + 去重，不额外调 API
    chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
    state["filtered_chunks"] = chunks[:10]
    ...
```

---

## 2. Policy Knowledge Tool 设计

### 2.1 架构约束

```
❌ PolicyAgent 直接 import PolicyRetriever
❌ PolicyAgent 直接连接 pgvector
✅ PolicyAgent → ToolGateway.invoke() → KnowledgeTool → PolicyRetriever → pgvector
```

### 2.2 KnowledgeTool 类

```python
# app/tools/knowledge_tool.py

class KnowledgeTool:
    """知识库统一访问工具
    
    所有 RAG 检索（政策/产业/文档）通过此类统一访问。
    不直接暴露给 Agent，Agent 通过 ToolGateway.invoke() 间接调用。
    """

    def __init__(self):
        self._retriever: PolicyRetriever | None = None

    @property
    def retriever(self) -> PolicyRetriever:
        if self._retriever is None:
            from app.services.retriever import PolicyRetriever
            self._retriever = PolicyRetriever()
        return self._retriever

    # ── ToolGateway 兼容的同步方法 ──

    def policy_hybrid_search_sync(self, params: dict) -> dict:
        """混合检索 — ToolGateway 调用入口"""
        import asyncio
        try:
            result = asyncio.run(self.retriever.hybrid_search(
                query=params.get("query", ""),
                top_k=params.get("top_k", 10),
                filters=params.get("filters"),
            ))
        except Exception as e:
            logger.error(f"KnowledgeTool search failed: {e}")
            # 降级到 Mock
            result = self._mock_fallback(params)
            result["mode"] = "mock_fallback"

        return {
            "status": "success",
            "tool": "policy_hybrid_search",
            "params": params,
            "result": {
                "chunks": [{
                    "chunk_id": c.get("chunk_id", ""),
                    "policy_id": c.get("policy_id", ""),
                    "title": c.get("metadata", {}).get("title", ""),
                    "content": c.get("content", ""),
                    "score": c.get("score", 0),
                    "search_method": c.get("search_method", "hybrid"),
                    "level": c.get("metadata", {}).get("level", ""),
                    "department": c.get("metadata", {}).get("department", ""),
                } for c in result],
                "total": len(result),
                "mode": result.get("mode", "pgvector") if isinstance(result, list) else "pgvector",
            }
        }

    def _mock_fallback(self, params: dict) -> list:
        """降级 Mock — 数据来自 adapters/policy_mock.py"""
        from app.tools.adapters.policy_mock import PolicyMockData
        return PolicyMockData.search(
            query=params.get("query", ""),
            filters=params.get("filters"),
            top_k=params.get("top_k", 10),
        )
```

### 2.3 ToolGateway 注册

```python
# gateway.py — _register_builtin_tools()

# === P1: KnowledgeTool 替换 Mock 政策搜索 ===
"policy_hybrid_search"   → knowledge_tool.policy_hybrid_search_sync,
"policy_vector_search"   → knowledge_tool.policy_hybrid_search_sync,  # 兼容旧名
"policy_metadata_search" → knowledge_tool.policy_hybrid_search_sync,  # 兼容旧名
"policy_query"           → knowledge_tool.policy_hybrid_search_sync,  # 兼容旧名

# PERMISSIONS 更新
"PolicyAgent": [
    "policy_hybrid_search",      # ⚡ 新
    "policy_vector_search",      # 保留兼容
    "policy_metadata_search",    # 保留兼容
    "enterprise_profile_get",    # 保留（P0）
],
```

---

## 3. pgvector Schema

### 3.1 新增 SQLAlchemy 模型

```python
# app/database/models/business.py — 追加

from pgvector.sqlalchemy import Vector

class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(String(50), ForeignKey("policy.policy_id"), nullable=True)
    filename = Column(String(500), nullable=False)
    file_format = Column(String(20))
    file_hash = Column(String(64))
    file_size = Column(Integer)
    page_count = Column(Integer)
    raw_text = Column(Text)
    parse_status = Column(String(20), default="pending")
    parse_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(100), unique=True, nullable=False)
    policy_id = Column(String(50), ForeignKey("policy.policy_id"), nullable=True)
    document_id = Column(Integer, ForeignKey("policy_documents.id"), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64))
    token_count = Column(Integer)
    embedding = Column(Vector(1536))           # ⚡ pgvector
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 3.2 索引 SQL

```sql
-- 向量索引 (10K+ chunks 时启用)
CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding 
    ON policy_chunks USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);

-- 业务索引
CREATE INDEX IF NOT EXISTS idx_policy_chunks_policy_id ON policy_chunks(policy_id);
```

### 3.3 与现有 Policy 表关系

```
policy ──1:N──→ policy_documents ──1:N──→ policy_chunks
  │                    │                        │
  │ (已有)             │ (新增)                 │ (新增, vector)
  │ policy_id          │ policy_id (FK)         │ policy_id (FK)
  │ title              │ filename               │ chunk_id
  │ level              │ raw_text               │ content
  │ department         │ parse_status           │ embedding ⚡
```

---

## 4. PDF Pipeline

### 4.1 Pipeline 组件

```
PDF/DOCX → DocumentParser → MetadataExtractor → TextChunker → EmbeddingService → VectorStore
```

### 4.2 各组件接口

```python
# app/services/document_parser.py
class DocumentParser:
    SUPPORTED = {".pdf", ".docx", ".html", ".txt"}

    async def parse(self, file_path: str) -> ParsedDocument:
        """PDF→pymupdf, DOCX→python-docx, HTML→BeautifulSoup"""
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            text, pages = self._parse_pdf(file_path)
        elif ext == ".docx":
            text, pages = self._parse_docx(file_path)
        return ParsedDocument(raw_text=text, page_count=pages, format=ext)

    def _parse_pdf(self, path: str):
        import fitz  # pymupdf
        doc = fitz.open(path)
        text = "\n\n".join(page.get_text() for page in doc)
        return text, len(doc)

# app/services/metadata_extractor.py
class MetadataExtractor:
    def extract(self, text: str, filename: str) -> PolicyMetadata:
        """
        从文本前 500 字符 + 文件名提取:
        - title: 文件名或首行
        - department: "工信厅"/"科技局" 等关键词匹配
        - level: "国家"/"广东省"/"广州市"/"区" 关键词
        - dates: 正则 (\\d{4}年\\d{1,2}月\\d{1,2}日)
        - scopes: "机器人"/"智能制造" 等产业关键词
        """
        ...

# app/services/chunker.py
class TextChunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: PolicyMetadata) -> List[ChunkData]:
        """章节感知分块"""
        sections = self._split_by_headings(text)  # 按"第X章"/"一、"分割
        chunks = []
        idx = 0
        for section_title, section_text in sections:
            for chunk_text in self._sliding_window(section_text):
                chunks.append(ChunkData(
                    chunk_id=f"{metadata.policy_id}-c{idx:03d}",
                    chunk_index=idx,
                    content=chunk_text,
                    content_hash=sha256(chunk_text),
                    metadata={"section": section_title, **metadata.to_dict()},
                ))
                idx += 1
        return chunks

# app/services/embedding.py
class EmbeddingService:
    def __init__(self, provider: str = "deepseek"):
        self.provider = provider

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量向量化 — 支持 OpenAI/DeepSeek"""
        ...

# app/services/vector_store.py
class VectorStore:
    async def upsert_chunks(self, chunks: List[ChunkData], embeddings: List[List[float]]):
        """批量 UPSERT 到 policy_chunks 表"""
        async with SessionLocal() as session:
            for chunk, emb in zip(chunks, embeddings):
                stmt = insert(PolicyChunk).values(
                    chunk_id=chunk.chunk_id, policy_id=chunk.metadata.get("policy_id"),
                    chunk_index=chunk.chunk_index, content=chunk.content,
                    content_hash=chunk.content_hash, embedding=emb,
                    metadata_=chunk.metadata,
                ).on_conflict_do_update(
                    index_elements=["chunk_id"],
                    set_={"embedding": emb, "content": chunk.content, "metadata_": chunk.metadata},
                )
                await session.execute(stmt)
            await session.commit()
```

### 4.3 政策导入命令

```bash
# backend/scripts/import_policies.py
python import_policies.py --dir docs/policies/         # 批量导入
python import_policies.py --file 广东省机器人行动计划.pdf  # 单文件
python import_policies.py --seed                         # 种子数据（8条预设）
```

---

## 5. Retriever 设计

### 5.1 PolicyRetriever

```python
# app/services/retriever.py

class PolicyRetriever:
    """政策检索引擎 — 唯一访问 pgvector 的地方"""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.mode = get_settings().policy_rag_mode  # "mock" | "pgvector"

    async def hybrid_search(
        self, query: str, top_k: int = 10, filters: dict = None
    ) -> dict:
        if self.mode == "mock":
            return self._mock_search(query, filters, top_k)

        # ── Step 1: 查询向量化 ──
        query_vec = await self.embedding_service.embed_batch([query])
        query_embedding = query_vec[0]

        # ── Step 2: pgvector cosine similarity ──
        sql = """
        SELECT 
            pc.chunk_id, pc.policy_id, pc.chunk_index, pc.content,
            1 - (pc.embedding <=> :query_vec) AS score,
            pc.metadata,
            'vector' AS search_method
        FROM policy_chunks pc
        JOIN policy p ON pc.policy_id = p.policy_id
        WHERE (:level IS NULL OR p.level = :level)
          AND (:department IS NULL OR p.department = :department)
          AND (:active_only = false OR p.status = 'active')
        ORDER BY pc.embedding <=> :query_vec
        LIMIT :top_k
        """
        # 执行 SQL，返回 chunks

        # ── Step 3: RRF 融合 (如果启用 keyword) ──
        # keyword_results = await self._keyword_search(query, filters, top_k)
        # merged = self._rrf_fuse(vector_results, keyword_results)

        return {
            "chunks": [...],
            "mode": "pgvector",
            "total": len(chunks),
        }

    async def _keyword_search(self, query, filters, top_k):
        """PostgreSQL full-text search"""
        sql = """
        SELECT ..., ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', :query)) AS score
        FROM policy_chunks
        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', :query)
        ORDER BY score DESC LIMIT :top_k
        """
        ...

    def _rrf_fuse(self, vec_results, kw_results, k=60):
        """Reciprocal Rank Fusion"""
        scores = {}
        for rank, item in enumerate(vec_results):
            scores[item.chunk_id] = 1.0 / (k + rank + 1)
        for rank, item in enumerate(kw_results):
            scores[item.chunk_id] = scores.get(item.chunk_id, 0) + 1.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]
```

### 5.2 查询性能目标

| 操作 | 目标延迟 |
|------|---------|
| 向量化 (1 query) | < 200ms (API) / < 50ms (本地) |
| pgvector 检索 (10K chunks) | < 20ms |
| pgvector 检索 (100K chunks) | < 50ms |
| hybrid RRF 融合 | < 10ms |
| **端到端** | **< 300ms** |

---

## 6. Policy Match API

### 6.1 端点设计

```python
# app/api/v1/business.py — 追加

@router.post("/policy/search")
async def policy_search(body: PolicySearchRequest):
    """
    政策智能检索
    
    Request Body:
    {
        "query": "机器人产业补贴",
        "enterprise_id": "ENT-001",    // 可选，用于重排
        "filters": {
            "level": "provincial",
            "region": "guangzhou",
            "industry": "机器人",
            "active_only": true
        },
        "top_k": 10,
        "search_mode": "hybrid"        // keyword | vector | hybrid
    }
    
    Response:
    {
        "success": true,
        "data": {
            "query": "机器人产业补贴",
            "total_matched": 5,
            "policies": [{
                "policy_id": "POL-001",
                "title": "广东省机器人产业集群行动计划(2024-2027)",
                "level": "provincial",
                "department": "广东省工信厅",
                "match_score": 0.92,
                "matched_chunks": [{
                    "chunk_id": "POL-001-c003",
                    "content": "...最高500万元补贴...",
                    "score": 0.92,
                    "search_method": "hybrid"
                }],
                "full_content": "..."    // 可选，按需返回
            }],
            "search_mode": "hybrid",
            "rag_mode": "pgvector"
        }
    }
    """
    ...

@router.post("/policy/match")
async def policy_match(body: PolicyMatchRequest):
    """
    企业政策自动匹配
    
    根据企业画像自动搜索适用政策，无需手动输入 query。
    内部: enterprise_profile → 提取 industry+location → hybrid_search
    
    Request: {"enterprise_id": "ENT-001", "top_k": 10}
    
    Response:
    {
        "success": true,
        "data": {
            "enterprise_id": "ENT-001",
            "enterprise_name": "广东博智林机器人",
            "industry": "建筑机器人",
            "location": "佛山",
            "matched_policies": [{
                "policy_id": "POL-001",
                "title": "...",
                "match_reason": "建筑机器人属于机器人产业重点支持方向",
                "match_score": 0.92
            }],
            "total_matched": 5
        }
    }
    """
    ...

@router.get("/policy/rag-status")
async def get_policy_rag_status():
    """
    RAG 系统状态
    
    Response:
    {
        "mode": "pgvector",              // mock | pgvector
        "total_documents": 12,
        "total_chunks": 456,
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "healthy": true
    }
    """
    ...
```

---

## 7. Mock/Production 双模式

### 7.1 配置驱动

```bash
# .env
POLICY_RAG_MODE=mock           # Demo 模式 (v1.1 行为)
# POLICY_RAG_MODE=pgvector     # 生产模式 (真实 pgvector)

POLICY_EMBEDDING_PROVIDER=deepseek
POLICY_EMBEDDING_MODEL=text-embedding-3-small
POLICY_EMBEDDING_DIMENSIONS=1536
```

### 7.2 切换逻辑

```python
# PolicyRetriever.__init__()
self.mode = get_settings().policy_rag_mode  # "mock" | "pgvector"

# hybrid_search()
if self.mode == "mock":
    return self._mock_search(...)    # → PolicyMockData (8条预设)
else:
    try:
        return self._pgvector_search(...)
    except Exception:
        logger.warning("pgvector 不可用，降级 Mock")
        return self._mock_search(...)  # 自动降级
```

### 7.3 PolicyMockData

```python
# app/tools/adapters/policy_mock.py
# 从 gateway.py _mock_policy_search() 迁移的 8 条预设政策
# 保持完全相同的搜索结果格式

class PolicyMockData:
    _POLICIES = [...]  # 8 条预设
    
    @classmethod
    def search(cls, query, filters, top_k):
        """与 v1.1 行为 100% 一致的关键词过滤"""
        results = cls._POLICIES
        if query:
            results = [p for p in results if query in p["title"] or query in p["summary"]]
        # ... filters ...
        return [{"content": p["summary"], "title": p["title"], "score": 0.9, ...} 
                for p in results[:top_k]]
```

---

## 8. 变更总览

### 8.1 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `app/tools/knowledge_tool.py` | ~100 | KnowledgeTool 核心类 |
| `app/tools/adapters/policy_mock.py` | ~100 | 8 条预设政策 Mock（从 gateway 迁移） |
| `app/services/__init__.py` | ~5 | Services 包 |
| `app/services/document_parser.py` | ~80 | PDF/DOCX 解析 |
| `app/services/metadata_extractor.py` | ~70 | 元数据提取 |
| `app/services/chunker.py` | ~80 | 章节感知分块 |
| `app/services/embedding.py` | ~100 | OpenAI/DeepSeek Embedding |
| `app/services/vector_store.py` | ~80 | pgvector 读写 |
| `app/services/retriever.py` | ~200 | PolicyRetriever (keyword/vector/hybrid) |
| `scripts/import_policies.py` | ~120 | CLI 政策导入工具 |

### 8.2 修改文件

| 文件 | 改动 | 行数变化 |
|------|------|---------|
| `gateway.py` | KnowledgeTool 注册；3 个 policy mock → KT | +15 |
| `policy_nodes.py` | vector_search → hybrid_search；metadata_filter 简化 | +15 |
| `business.py` (models) | +PolicyDocument, +PolicyChunk 模型 | +35 |
| `business.py` (API) | +3 个 API 端点 | +80 |
| `config.py` | +4 配置项 | +6 |
| `.env.example` | RAG 配置 | +8 |
| `executor.py` | PolicyAgent 调用不变 | 0 |

### 8.3 代码统计

| 类别 | 文件 | 行数 |
|------|------|------|
| 新增 | 10 | ~935 |
| 修改 | 6 | ~159 |
| **合计** | **16** | **~1,094** |

### 8.4 不变的部分（保证兼容）

- PolicyAgent 6 节点 Pipeline ✅
- PolicyState 输入/输出格式 ✅
- executor.py 调用 PolicyAgent ✅
- response_formatter 输出格式 ✅
- Supervisor INTENT_ROUTING ✅
- Docker Compose 部署 ✅
- ENTERPRISE_DATA_SOURCE=mock ✅

---

## 9. 验收清单

- [ ] `KnowledgeTool.policy_hybrid_search_sync()` 返回正确格式
- [ ] Gateway `policy_hybrid_search` 注册成功
- [ ] PolicyAgent 6 节点全链路通过（mock 模式）
- [ ] PolicyAgent 6 节点全链路通过（pgvector 模式，有种子数据）
- [ ] PDF 解析 → 分块 → Embedding → pgvector 写入全流程
- [ ] `import_policies.py --seed` 导入 8 条预设政策
- [ ] `/policy/search` API 返回正确 JSON
- [ ] `/policy/match` API 基于企业画像自动匹配
- [ ] `POLICY_RAG_MODE=mock` → 行为与 v1.1 一致
- [ ] pgvector 不可用 → 自动降级 Mock

---

*Generated by Hermes Agent · 2026-07-23 · Policy RAG Technical Design Review V1.0*
