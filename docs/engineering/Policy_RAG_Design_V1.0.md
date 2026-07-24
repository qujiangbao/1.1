# Policy RAG + pgvector — Technical Design V1.0

> **P1 Technical Design Review**  
> **版本**: v1.0  
> **基准**: v1.1 Competition Gold + P0 Enterprise Data Tool  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-23

---

## 目录

1. [现状审计](#1-现状审计)
2. [数据来源设计](#2-数据来源设计)
3. [文档处理 Pipeline](#3-文档处理-pipeline)
4. [pgvector 数据库设计](#4-pgvector-数据库设计)
5. [Retriever 设计](#5-retriever-设计)
6. [PolicyAgent 调用链](#6-policyagent-调用链)
7. [Mock/Production 双模式](#7-mockproduction-双模式)
8. [API 设计](#8-api-设计)
9. [与现有代码集成点](#9-与现有代码集成点)
10. [文件结构 & 变更估算](#10-文件结构--变更估算)

---

## 1. 现状审计

### 1.1 现有 PolicyAgent (policy_nodes.py)

```
query_analyzer → enterprise_loader → vector_search → metadata_filter → policy_matcher → response_formatter
       ↓                ↓                  ↓                  ↓                ↓                ↓
   解析意图         加载企业画像        ToolGateway         区域过滤         相似度排序       组装报告
                                     .invoke(
                                       "policy_vector_search")
```

**问题**: `vector_search_node` 调用的是 ToolGateway 的 `_mock_policy_search()`，返回 8 条硬编码政策 JSON。

### 1.2 现有数据库

```sql
-- 已有（但无 embedding）
policy (
    policy_id VARCHAR(50) PK,
    title VARCHAR(500),
    level VARCHAR(30),      -- national/provincial/municipal/district
    department VARCHAR(200),
    category VARCHAR(100),
    industry_scope TEXT[],
    region_scope TEXT[],
    content TEXT,
    publish_date DATE,
    expire_date DATE,
    status VARCHAR(30),
    source VARCHAR(500)
)
```

**缺失**: 无 `policy_documents`（原始文档表）、无 `policy_chunks`（分块+向量表）、无 embedding 列。

### 1.3 ToolGateway 政策工具

```python
# 3 个工具，全部指向同一个 mock
"policy_vector_search"    → _mock_policy_search()   # 返回硬编码 8 条政策
"policy_metadata_search"  → _mock_policy_search()
"policy_query"            → _mock_policy_search()
```

### 1.4 Docker 环境

```yaml
# docker-compose.yml 已配置
postgres:
  image: pgvector/pgvector:pg16   # ✅ pgvector extension 已就绪
```

---

## 2. 数据来源设计

### 2.1 四级政策体系

```
国家政策 (national)
├── 工信部: 十四五机器人产业发展规划
├── 科技部: 关于加快培育发展制造业优质企业的指导意见
└── 国务院: 中国制造2025

广东省政策 (provincial)
├── 广东省工信厅: 机器人产业集群行动计划(2024-2027)
├── 广东省发改委: 战略性产业集群「链主」企业遴选
└── 广东省政府: 制造业数字化转型实施方案

广州市政策 (municipal)
├── 广州市科技局: 人工智能产业扶持办法
├── 广州市科技局: 科技型中小企业技术创新基金
└── 广州市商务局: 总部企业认定奖励

产业园政策 (district/park)
├── 黄埔区工信局: 促进智能制造发展办法
├── 园区管委会: 入驻企业租金补贴
└── 园区招商局: 重点产业扶持资金
```

### 2.2 数据获取方式

| 来源 | 格式 | 获取方式 | 更新频率 |
|------|------|---------|---------|
| 政府官网 | PDF/HTML | 爬虫/手动下载 | 政策发布时 |
| 政策数据库 API | JSON | 第三方 API（可选） | 每日同步 |
| 园区内部文件 | DOCX/PDF | 手动上传 | 按需 |

### 2.3 初始种子数据

P1 实现时保留 v1.1 的 8 条预设政策作为种子数据，通过 `import_policies.py` 脚本导入 pgvector。

---

## 3. 文档处理 Pipeline

### 3.1 Pipeline 全貌

```
PDF/DOCX/HTML
    ↓
[1] DocumentParser       — 格式解析 → 纯文本
    ├── PDF: PyMuPDF (pymupdf)
    ├── DOCX: python-docx
    └── HTML: BeautifulSoup
    ↓
[2] MetadataExtractor    — 提取结构化元数据
    ├── 标题 (title)
    ├── 发文部门 (department)
    ├── 级别 (level): national/provincial/municipal/district
    ├── 发布日期 (publish_date)
    ├── 失效日期 (expire_date)
    ├── 行业范围 (industry_scope)
    └── 地区范围 (region_scope)
    ↓
[3] TextChunker          — 文本分块
    ├── 策略: 章节感知 + 滑动窗口
    ├── chunk_size: 512 tokens (≈ 1200 中文字符)
    ├── overlap: 50 tokens
    └── 保留章节标题作为上下文
    ↓
[4] EmbeddingService     — 文本向量化
    ├── 主: DeepSeek Embedding (或 OpenAI text-embedding-3-small)
    ├── 备: BGE-M3 本地模型
    └── 维度: 1536 (OpenAI) / 1024 (BGE-M3)
    ↓
[5] VectorStore          — 写入 pgvector
    ├── 表: policy_chunks
    ├── 索引: IVFFlat (10K+) / HNSW (100K+)
    └── 批量 UPSERT
```

### 3.2 各组件接口

```python
# app/services/document_parser.py
class DocumentParser:
    async def parse(self, file_path: str) -> ParsedDocument:
        """返回: {raw_text, metadata, page_count, format}"""
        ...

# app/services/metadata_extractor.py  
class MetadataExtractor:
    def extract(self, text: str, filename: str) -> PolicyMetadata:
        """从文本+文件名提取: title, department, level, dates, scopes"""
        ...

# app/services/chunker.py
class TextChunker:
    def chunk(self, text: str, metadata: PolicyMetadata) -> List[Chunk]:
        """章节感知分块，返回 [{chunk_index, content, metadata, tokens}]"""
        ...

# app/services/embedding.py
class EmbeddingService:
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """批量向量化，支持批量 API 调用"""
        ...

# app/services/vector_store.py
class VectorStore:
    async def upsert_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]):
        """写入 policy_chunks 表"""
        ...
    async def delete_policy(self, policy_id: str):
        """删除某政策的所有分块"""
        ...
```

### 3.3 Chunk 结构

```python
@dataclass
class Chunk:
    chunk_id: str              # "POL-001-chunk-003"
    policy_id: str             # "POL-001"
    chunk_index: int           # 3
    content: str               # 分块文本
    content_hash: str          # SHA256 (去重用)
    token_count: int           # token 数
    metadata: dict             # {section_title, page_num, ...}
```

---

## 4. pgvector 数据库设计

### 4.1 新增表

#### policy_documents（原始文档表）

```sql
CREATE TABLE policy_documents (
    id              SERIAL PRIMARY KEY,
    policy_id       VARCHAR(50) REFERENCES policy(policy_id),
    filename        VARCHAR(500) NOT NULL,        -- 原始文件名
    file_format     VARCHAR(20),                  -- pdf/docx/html
    file_hash       VARCHAR(64),                  -- SHA256 去重
    file_size       INTEGER,                      -- 字节数
    page_count      INTEGER,
    raw_text        TEXT,                         -- 解析后全文
    parse_status    VARCHAR(20) DEFAULT 'pending', -- pending/parsed/failed
    parse_error     TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

#### policy_chunks（分块+向量表）⭐ 核心表

```sql
CREATE TABLE policy_chunks (
    id              SERIAL PRIMARY KEY,
    chunk_id        VARCHAR(100) UNIQUE NOT NULL,  -- "POL-001-c003"
    policy_id       VARCHAR(50) REFERENCES policy(policy_id),
    document_id     INTEGER REFERENCES policy_documents(id),
    chunk_index     INTEGER NOT NULL,              -- 分块序号
    content         TEXT NOT NULL,                 -- 分块文本
    content_hash    VARCHAR(64),                   -- SHA256
    token_count     INTEGER,
    embedding       vector(1536),                  -- ⭐ pgvector 向量
    metadata        JSONB DEFAULT '{}',            -- {section, page, level, department}
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_policy_chunks_policy_id ON policy_chunks(policy_id);
CREATE INDEX idx_policy_chunks_embedding ON policy_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### policy_embedding_config（配置表）

```sql
CREATE TABLE policy_embedding_config (
    id              SERIAL PRIMARY KEY,
    model_name      VARCHAR(100),                   -- "text-embedding-3-small"
    dimensions      INTEGER,                        -- 1536
    provider        VARCHAR(50),                    -- "openai" | "deepseek" | "local"
    is_active       BOOLEAN DEFAULT false,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.2 向量索引策略

| 数据量 | 索引类型 | 参数 | 查询延迟 |
|--------|---------|------|---------|
| < 10K chunks | 无需索引（顺序扫描） | — | < 5ms |
| 10K–100K | IVFFlat | lists=100 | < 20ms |
| 100K+ | HNSW | m=16, ef_construction=200 | < 10ms |

### 4.3 与现有 Policy 表的关系

```
policy_documents.doc_id ──→ policy.policy_id (FK)
policy_chunks.policy_id ──→ policy.policy_id (FK)
policy_chunks.document_id → policy_documents.id (FK)
```

### 4.4 Embedding 模型选择

```python
# config.py
POLICY_EMBEDDING_PROVIDER=deepseek     # openai | deepseek | local
POLICY_EMBEDDING_MODEL=text-embedding-3-small
POLICY_EMBEDDING_DIMENSIONS=1536
```

---

## 5. Retriever 设计

### 5.1 三种检索模式

```
PolicyRetriever
├── keyword_search(query)           → 关键词检索 (PostgreSQL full-text)
├── vector_search(query, top_k)     → 语义检索 (pgvector cosine)
└── hybrid_search(query, filters)   → 混合检索 (RRF 融合)
```

### 5.2 检索接口

```python
# app/services/retriever.py

class PolicyRetriever:
    """企业政策检索引擎"""
    
    async def keyword_search(
        self, query: str, 
        filters: PolicyFilter = None, 
        limit: int = 10
    ) -> List[RetrievedChunk]:
        """
        PostgreSQL full-text search (tsvector)
        适合: 精确政策名称、发文部门、政策编号
        """
        ...

    async def vector_search(
        self, query: str,
        top_k: int = 10,
        filters: PolicyFilter = None
    ) -> List[RetrievedChunk]:
        """
        pgvector cosine similarity
        SQL: SELECT *, 1 - (embedding <=> query_embedding) AS similarity
             FROM policy_chunks ORDER BY similarity DESC LIMIT $top_k
        
        适合: 语义理解查询 "机器人产业补贴"、"智能制造扶持"
        """
        ...

    async def hybrid_search(
        self, query: str,
        top_k: int = 10,
        filters: PolicyFilter = None,
        keyword_weight: float = 0.3,
        vector_weight: float = 0.7
    ) -> List[RetrievedChunk]:
        """
        RRF (Reciprocal Rank Fusion) 混合检索
        
        流程:
        1. keyword_search → rank_k[i] = 1/(k + keyword_rank[i])
        2. vector_search  → rank_v[i] = 1/(k + vector_rank[i])
        3. score[i] = keyword_weight * rank_k[i] + vector_weight * rank_v[i]
        4. 按 score 降序取 top_k
        """
        ...

    async def rerank(
        self, chunks: List[RetrievedChunk],
        enterprise_profile: dict
    ) -> List[RetrievedChunk]:
        """
        基于企业画像重排序
        - 行业匹配加分
        - 地区匹配加分
        - 政策时效性加权
        """
        ...

@dataclass
class PolicyFilter:
    level: Optional[str] = None        # national/provincial/municipal/district
    department: Optional[str] = None   # 发文部门
    industry: Optional[str] = None     # 企业行业
    region: Optional[str] = None       # 企业所在地
    active_only: bool = True           # 仅有效政策
    publish_after: Optional[date] = None

@dataclass 
class RetrievedChunk:
    chunk_id: str
    policy_id: str
    chunk_index: int
    content: str
    score: float                       # 相似度 0-1
    metadata: dict                     # {title, level, department, section}
    search_method: str                 # "keyword" | "vector" | "hybrid"
```

### 5.3 检索流程

```
User: "广州机器人企业有什么补贴政策？"
    ↓
1. EmbeddingService.embed("广州机器人企业有什么补贴政策？")
    → query_vector: [0.023, -0.451, ...]
    ↓
2. PolicyRetriever.hybrid_search(
      query_vector,
      filters=PolicyFilter(region="guangzhou", industry="机器人")
   )
    ↓
3. pgvector: cosine similarity + ts_rank
    ↓
4. 返回 Top 10 chunks，每个含 score + metadata
    ↓
5. PolicyRetriever.rerank(chunks, enterprise_profile_of_user)
    → 行业"机器人"的企业，机器人政策权重 ↑
    → 地区"广州"的企业，广州政策权重 ↑
    ↓
6. PolicyMatcher: chunks → policies (去重、聚合、排序)
    ↓
7. ResponseFormatter: 组装报告
```

---

## 6. PolicyAgent 调用链

### 6.1 架构约束

```
❌ 禁止: PolicyAgent 直接访问 pgvector
✅ 必须: PolicyAgent → ToolGateway → KnowledgeTool → pgvector
```

### 6.2 完整调用链

```
PolicyAgent (policy_nodes.py)
    │
    ├── query_analyzer_node()
    │     └── 提取 query, enterprise_id, filters
    │
    ├── enterprise_loader_node()
    │     └── tg.invoke("PolicyAgent", "enterprise_profile_get", ...)
    │           └── EnterpriseDataTool (P0) → 企业画像
    │
    ├── vector_search_node()        ← ⚡ 改造点
    │     └── tg.invoke("PolicyAgent", "policy_hybrid_search", {
    │           query, top_k, filters:{level, region, industry}
    │         })
    │           └── KnowledgeTool.policy_search()
    │                 └── PolicyRetriever.hybrid_search()
    │                       └── pgvector
    │
    ├── metadata_filter_node()      ← ⚡ 改造点
    │     └── 不再调用独立 metadata_search
    │     └── 对 vector_search 结果进行内存过滤
    │
    ├── policy_matcher_node()       ← 保留
    │     └── 去重、聚合 chunk → policy
    │     └── PolicyRetriever.rerank()
    │
    └── response_formatter_node()   ← 保留
          └── 组装 PolicyReport
```

### 6.3 KnowledgeTool 设计

```python
# app/tools/knowledge_tool.py (新建)

class KnowledgeTool:
    """知识库统一访问工具 — Policy/Industry/... 所有 RAG 的统一入口"""
    
    def __init__(self):
        self._retriever = None
    
    @property
    def retriever(self) -> PolicyRetriever:
        if self._retriever is None:
            self._retriever = PolicyRetriever()
        return self._retriever
    
    def policy_search_sync(self, params: dict) -> dict:
        """同步包装 → ToolGateway"""
        import asyncio
        result = asyncio.run(self.policy_search(
            query=params.get("query", ""),
            top_k=params.get("top_k", 10),
            filters=params.get("filters"),
        ))
        return {"status": "success", "chunks": result, "total": len(result)}
    
    async def policy_search(self, query, top_k=10, filters=None):
        return await self.retriever.hybrid_search(query, top_k, filters)
```

### 6.4 ToolGateway 注册

```python
# gateway.py — PERMISSIONS 更新 + Tool 注册

PERMISSIONS = {
    ...
    "PolicyAgent": [
        "policy_hybrid_search",      # ⚡ 新: 混合检索
        "policy_keyword_search",     # ⚡ 新: 关键词检索
        "enterprise_profile_get",    # 保留
    ],
}

# _register_builtin_tools
"policy_hybrid_search"  → knowledge_tool.policy_search_sync,
"policy_keyword_search" → knowledge_tool.policy_keyword_search_sync,
"policy_vector_search"  → knowledge_tool.policy_search_sync,  # 兼容旧名称
"policy_metadata_search"→ knowledge_tool.policy_search_sync,  # 兼容旧名称
```

---

## 7. Mock/Production 双模式

### 7.1 模式切换

```bash
# .env
POLICY_RAG_MODE=mock         # Demo 模式（v1.1 预设数据）
POLICY_RAG_MODE=pgvector     # 生产模式（pgvector 真实检索）
```

### 7.2 双模式实现

```python
# app/services/retriever.py

class PolicyRetriever:
    def __init__(self, mode: str = None):
        self.mode = mode or get_settings().policy_rag_mode
    
    async def hybrid_search(self, query, top_k, filters):
        if self.mode == "mock":
            return self._mock_search(query, filters, top_k)  # v1.1 逻辑
        else:
            return self._pgvector_search(query, filters, top_k)  # 真实 pgvector
    
    def _mock_search(self, query, filters, top_k):
        """保留 v1.1 Mock 逻辑 — 从 adapters/policy_mock.py 加载"""
        from app.tools.adapters.policy_mock import PolicyMockData
        return PolicyMockData.search(query, filters, top_k)
```

### 7.3 降级策略

```
POLICY_RAG_MODE=pgvector
    ├── pgvector 可用 → 真实检索 ✅
    ├── pgvector 无数据 (0 chunks) → 降级 Mock + WARNING
    └── DB 连接失败 → 降级 Mock + ERROR log
```

---

## 8. API 设计

### 8.1 新增端点

```python
# app/api/v1/business.py 扩展

@router.post("/policy/search")
async def policy_search(body: PolicySearchRequest):
    """
    政策智能检索
    
    Request:
    {
      "query": "机器人产业补贴政策",
      "enterprise_id": "ENT-001",       // 可选: 基于企业画像重排
      "filters": {
        "level": "provincial",          // national/provincial/municipal/district
        "region": "guangzhou",
        "industry": "机器人",
        "active_only": true
      },
      "top_k": 10,
      "search_mode": "hybrid"           // keyword | vector | hybrid
    }
    
    Response:
    {
      "success": true,
      "data": {
        "query": "机器人产业补贴政策",
        "total_chunks": 25,
        "policies": [
          {
            "policy_id": "POL-001",
            "title": "广东省机器人产业集群行动计划(2024-2027)",
            "level": "provincial",
            "department": "广东省工信厅",
            "matched_chunks": [{
              "chunk_id": "POL-001-c003",
              "content": "...对入驻产业园企业给予最高500万元补贴...",
              "score": 0.92,
              "search_method": "hybrid"
            }],
            "relevance_score": 0.92
          }
        ],
        "search_mode": "hybrid",
        "rag_mode": "pgvector"
      }
    }
    """
    ...

@router.post("/policy/match")
async def policy_match(body: PolicyMatchRequest):
    """
    企业政策匹配 — 根据企业画像自动匹配适用政策
    
    Request:
    {
      "enterprise_id": "ENT-001",
      "top_k": 10
    }
    
    Response:
    {
      "success": true,
      "data": {
        "enterprise_id": "ENT-001",
        "enterprise_name": "广东博智林机器人",
        "industry": "建筑机器人",
        "location": "佛山",
        "matched_policies": [
          {
            "policy_id": "POL-001",
            "title": "...",
            "match_reason": "企业属于机器人产业，符合省级产业扶持范围",
            "match_score": 95,
            "applicable_chunks": [...]
          }
        ],
        "total_matched": 5
      }
    }
    """
    ...

@router.get("/policy/{policy_id}")
async def get_policy_detail(policy_id: str):
    """获取单条政策完整内容 + 所有分块"""
    ...

@router.get("/policy/rag-status")
async def get_rag_status():
    """
    RAG 系统状态
    
    Response:
    {
      "mode": "pgvector",
      "total_documents": 12,
      "total_chunks": 456,
      "embedding_model": "text-embedding-3-small",
      "embedding_dimensions": 1536,
      "last_import": "2026-07-23T10:00:00",
      "healthy": true
    }
    """
    ...
```

### 8.2 政策导入 API

```python
@router.post("/policy/import")
async def import_policy_document(
    file: UploadFile,
    title: str = Form(...),
    level: str = Form("provincial"),
    department: str = Form(...),
):
    """
    上传政策文档 → Pipeline → pgvector
    
    Request: multipart/form-data
    - file: PDF/DOCX
    - title: 政策标题
    - level: national/provincial/municipal/district
    - department: 发文部门
    """
    ...
```

---

## 9. 与现有代码集成点

### 9.1 修改清单

| 文件 | 改动 | 影响 |
|------|------|------|
| `policy_nodes.py` | vector_search_node → `policy_hybrid_search` | ⚡ 核心改动 |
| `gateway.py` | 注册 KnowledgeTool；更新 PolicyAgent 权限 | 🟡 中等 |
| `business.py` | Policy 模型不变；新增 policy_documents/chunks 表 | 🟡 新增 |
| `business.py` (API) | 5 个新端点 | 🟡 新增 |
| `config.py` | 5 个新配置项 | 🟢 小 |
| `.env.example` | RAG 配置 | 🟢 小 |
| `executor.py` | PolicyAgent summary 格式不变 | 🟢 无改动 |

### 9.2 不变的部分

- `PolicyAgent` 6 节点 Pipeline 结构不变
- `ToolGateway.invoke()` 接口不变
- `Supervisor INTENT_ROUTING` 不变
- `enterprise_loader_node()` 不变（已对接 P0 EnterpriseDataTool）
- `response_formatter_node()` 输出格式不变

### 9.3 向后兼容

```
POLICY_RAG_MODE=mock:
  → KnowledgeTool 返回 v1.1 Mock 数据
  → 完全兼容现有 Demo

POLICY_RAG_MODE=pgvector + 无数据:
  → 自动降级到 Mock
  → 不阻断流程
```

---

## 10. 文件结构 & 变更估算

```
backend/app/
├── services/                          ← 新建目录
│   ├── __init__.py
│   ├── document_parser.py             ← PDF/DOCX/HTML 解析    (~120 行)
│   ├── metadata_extractor.py          ← 元数据提取            (~80 行)
│   ├── chunker.py                     ← 文本分块              (~100 行)
│   ├── embedding.py                   ← Embedding 服务        (~150 行)
│   ├── vector_store.py                ← pgvector 读写         (~120 行)
│   └── retriever.py                   ← 检索引擎              (~250 行)
│
├── tools/
│   ├── knowledge_tool.py              ← KnowledgeTool 核心    (~120 行)
│   └── adapters/
│       └── policy_mock.py             ← 政策 Mock 数据        (~180 行)
│
├── api/v1/
│   └── business.py                    ← +5 个 API 端点        (+100 行)
│
├── database/models/
│   └── business.py                    ← +2 个新表             (+50 行)
│
└── scripts/
    └── import_policies.py             ← 政策导入 CLI          (~150 行)

# 修改文件
├── tools/gateway.py                   ← +KnowledgeTool 注册   (+30 行)
├── langgraph/nodes/policy_nodes.py    ← 检索改造              (+20 行)
├── config.py                          ← +5 配置项            (+8 行)
└── .env.example                       ← RAG 配置             (+10 行)
```

### 变更统计

| 类别 | 文件数 | 行数 |
|------|--------|------|
| 新建 | 10 | ~1,320 |
| 修改 | 4 | ~68 |
| **合计** | **14** | **~1,388** |

---

## 11. 验收清单

- [ ] PDF 政策文档成功解析 → 文本 + 元数据
- [ ] 分块保留章节上下文 + 元数据
- [ ] Embedding 生成成功（OpenAI/DeepSeek/本地）
- [ ] pgvector 写入 + IVFFlat 索引 < 100ms 查询
- [ ] `hybrid_search("机器人补贴")` 返回 5+ 相关结果
- [ ] `POLICY_RAG_MODE=mock` → 行为与 v1.1 完全一致
- [ ] PolicyAgent 6 节点 Pipeline 全部通过
- [ ] 5 个新 API 端点返回正确 JSON
- [ ] `policy/import` 上传 PDF 全流程通
- [ ] P0 EnterpriseDataTool 不受影响

---

*Generated by Hermes Agent · 2026-07-23 · Policy RAG Design V1.0*
