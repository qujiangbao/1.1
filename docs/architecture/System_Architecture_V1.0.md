# Industrial Park Agent System Architecture V1.0

> 状态：FROZEN  
> 日期：2026-07-28  
> 适用范围：Industrial Park Agent 与 Policy Intelligence Pipeline 的整合  
> 架构唯一事实来源：`D:\industrial-park-v1.1\docs\ARCHITECTURE.md`

本文档提供一个稳定的、面向整合任务的架构入口。它不创建第二套架构；如与
`docs\ARCHITECTURE.md` 冲突，以后者为准，并立即停止实现、提交冲突说明。

## 1. 系统目标

Industrial Park Agent 是面向产业园区的 7×24 小时 AI 产业运营团队。Policy
Intelligence Pipeline 的作用，是把可核验的政府政策转化为 Policy Agent 可检索、
可引用、可追踪的政策知识，而不是再造一个独立政策系统。

## 2. 冻结的系统边界

### 2.1 在线控制流

```text
User / Browser
      |
FastAPI API Gateway
      |
LangGraph Supervisor
      |
Policy Agent
      |
TaskResult
      |
Supervisor
      |
User / Browser
```

Supervisor 是唯一业务调度中心。Policy Agent 不调用其他业务 Agent；业务 Agent
之间也不直接通信。

### 2.2 在线数据访问流

```text
Policy Agent
      |
Tool Gateway: policy_hybrid_search
      |
KnowledgeTool
      |
PolicyRetriever
      |
      +-- crawl4ai mode --> validated local snapshot/catalog
      |
      +-- pgvector mode --> PostgreSQL policy / policy_documents /
                            policy_chunks + pgvector HNSW
```

Tool Gateway 是 Agent 的唯一数据访问边界，不是第二个 Supervisor。Policy Agent
不得直接读取文件、直接查询 PostgreSQL/pgvector、调用爬虫或启动 Docling。

### 2.3 离线政策入库流

```text
gz.gov.cn / approved government sources
      |
Crawl4AI crawler (D:\crawl4ai-tools)
      |
versioned snapshot/raw + _raw_manifest.json
      |                         \
      |                          \ attachments / complex documents
baseline cleaning                 document router
      |                                |
snapshot/clean                     Docling offline worker
      |                                |
      +------------ canonical validated artifact
                           |
                  _clean_manifest.json
                  _clean_report.json
                  _catalog.json
                           |
          +----------------+----------------+
          |                                 |
local snapshot retrieval           optional ingestion job
                                            |
                                  PolicyIngestionService
                                            |
                         policy / policy_documents / policy_chunks
```

`policy_raw` 是上述 `snapshot/raw`、附件及 `_raw_manifest.json` 组成的逻辑原始层，
不是新的数据库表。当前数据库模型冻结，禁止仅因名称需要新增 `policy_raw` 表。

Docling 只作为离线异步增强解析器。HTML 正文和简单文档继续走现有轻量基线；
Docling 成功时使用增强结果，失败、超时或结果不完整时保留并使用基线结果。

## 3. 组件职责

| 组件 | 唯一职责 | 明确禁止 |
|---|---|---|
| Supervisor | 意图识别、任务规划、Agent 调度、结果聚合 | 直接实现政策解析或检索 |
| Policy Agent | 组织政策查询、匹配和带证据回答 | 直连 DB、文件系统、爬虫、Docling |
| Tool Gateway | 权限、参数、调用与 Trace 边界 | 承担业务编排或文档解析 |
| KnowledgeTool / PolicyRetriever | 统一政策检索，屏蔽存储模式 | 在 Agent 中暴露数据库实现 |
| Crawl4AI 工具 | 官方来源发现、抓取、快照和原始清单 | 在线用户请求时运行、直接写业务表 |
| Cleaner / Catalog Builder | 正文清洗、元数据、相关性和运行目录 | 丢弃原始证据或伪造缺失字段 |
| Docling worker | 复杂附件的离线结构化增强 | 替换轻量基线、进入实时链路、启用未批准 OCR |
| Ingestion job | 幂等写入既有政策表和向量 | 由 Agent 触发、绕过既有 service 层 |

## 4. 冻结契约

1. Supervisor 七节点结构不可增删；仅允许在现有节点内部增加兼容性
   hooks/filters。
2. 业务 Agent 调用接口保持
   `execute_business_agent(agent_name, task, state)`。
3. Policy Agent 的政策检索入口保持 Tool Gateway；
   当前主入口为 `policy_hybrid_search`，旧名称只作兼容别名。
4. 不新增业务 Agent，不把 Docling 设计成 Agent。
5. 不新建重复政策表；沿用 `policy`、`policy_documents`、`policy_chunks`。
6. 在线查询不实时访问政府网站，不同步运行 Docling。
7. 原始文件、来源 URL、抓取时间、SHA-256、解析器版本和解析状态必须可追踪。
8. 不生成 mock embedding 或伪造政策字段；未知值保持未知。
9. 不保存 API Key，不覆盖 `.env`、`.env.production` 或用户未提交修改。
10. `main` 分支和现有脏工作区不可 reset、clean、checkout 覆盖。

## 5. 允许的整合扩展

在不改变上述边界时，可以：

- 在基础设施层增加文档分类器、Docling worker adapter、离线队列或 runner；
- 扩展现有快照 manifest 的可选解析元数据；
- 扩展 `PolicyIngestionService` 对增强正文的选择与审计；
- 在 Tool Gateway 后方增强 Retriever，但保持工具名称与返回结构兼容；
- 新增测试、运行手册、指标和失败回退逻辑。

任何数据库迁移、Supervisor 图结构变更、Agent 接口变更、OCR 方案或生产模型变更，
都必须单独设计、单独审批，不属于 Policy Pipeline Integration V1.0。

## 6. 数据可信度与降级

优先级如下：

```text
官方原始文件
  > Docling 成功且通过校验的增强正文
  > 轻量基线正文
  > 仅元数据记录
  > 不可用（明确返回 data_available=false）
```

不得为了“链路跑通”用 LLM 补写政策原文、金额、截止日期、申报条件或来源。
Docling 失败不得阻断基线入库和在线查询。

## 7. 变更判定

以下任一情况出现时，停止编码并请求架构确认：

- 需要新增或删除 Supervisor 节点；
- 需要 Policy Agent 直接连接数据库或读取本地快照；
- 需要在用户请求期间抓取网站或启动 Docling；
- 需要新建政策相关业务表；
- 需要启用 OCR、TableFormerV2 或来源不明的模型；
- 需要修改冻结接口或删除现有回退模式。

## 8. 必读关联文档

1. `D:\industrial-park-v1.1\docs\ARCHITECTURE.md`
2. `D:\industrial-park-v1.1\docs\architecture\Supervisor_Technical_Design_V1.1.md`
3. `D:\industrial-park-v1.1\docs\architecture\Tool_Gateway_Design_V1.0.md`
4. `D:\industrial-park-v1.1\docs\agents\Policy_RAG_Workflow_V1.0.md`
5. `D:\industrial-park-v1.1\docs\engineering\Policy_Pipeline_Integration_Task.md`
6. `D:\docling-policy-poc\接手文档.md`

