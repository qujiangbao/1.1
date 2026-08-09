# Industrial Park Agent — Project Context

> 所有 AI/Hermes/Codex 接手入口  
> 更新时间：2026-07-28  
> 主项目：`D:\industrial-park-v1.1`

## 0. 当前任务

```text
Policy Intelligence Pipeline V1.0 integration
```

核心指令：

> 不要重新开发爬虫和 Docling。把它们作为已有基础设施，接入 Industrial Park
> Agent 的 Policy Intelligence Pipeline。

## 1. 项目目标

Industrial Park Agent 是面向产业园区的 7×24 小时 AI 产业运营团队，不是单一
Chatbot。系统由 Supervisor 统一编排多个专业 Agent，Policy Agent 负责把真实、
可引用的政策知识转化为政策查询、企业匹配和申报建议。

## 2. 必读顺序

1. `D:\industrial-park-v1.1\POLICY_PIPELINE_EXECUTION_HANDOFF.md`
2. `D:\industrial-park-v1.1\AI_HANDOFF.md`
3. `D:\industrial-park-v1.1\docs\PROJECT_CONTEXT.md`
4. `D:\industrial-park-v1.1\docs\ARCHITECTURE.md`
5. `D:\industrial-park-v1.1\docs\architecture\System_Architecture_V1.0.md`
6. `D:\industrial-park-v1.1\docs\engineering\Policy_Pipeline_Integration_Task.md`
7. `D:\industrial-park-v1.1\docs\engineering\Codex_Project_Handoff_2026-07-28.md`
8. `D:\docling-policy-poc\接手文档.md`
9. `D:\crawl4ai-tools\README.md`

发生冲突时的优先级：

```text
用户最新明确指令
  > docs/ARCHITECTURE.md 的冻结约束
  > Policy_Pipeline_Integration_Task.md
  > 当前代码与测试所证明的事实
  > 历史 handoff / archive 文档
```

发现冲突应记录并询问，不得静默选择新的架构。

## 3. 三个项目的角色

| 项目 | 角色 | 不应承担 |
|---|---|---|
| `D:\industrial-park-v1.1` | 主系统、Supervisor、Policy Agent、Tool Gateway、知识库与最终验收 | 重写外部基础设施 |
| `D:\crawl4ai-tools` | 官方政策发现、抓取、版本化快照、清洗 | Agent 编排、在线查询、直接写业务数据库 |
| `D:\docling-policy-poc` | 复杂文档离线增强解析与已验证 worker | 实时 API、Policy Agent、替换轻量基线 |

## 4. 已完成

- [x] FastAPI + Next.js 主系统；
- [x] LangGraph Supervisor 与六个业务 Agent；
- [x] Tool Gateway 和 Agent-Tool 权限边界；
- [x] Policy Agent / Policy RAG 查询链路；
- [x] 广州政府多来源 Crawl4AI 抓取；
- [x] 版本化 raw/clean 政策快照和运行 catalog；
- [x] local snapshot 检索模式；
- [x] PostgreSQL/pgvector schema 与 ingestion 代码；
- [x] Docling PDF/DOCX/.doc PoC 和复杂文档子场景验证；
- [x] Docling 的 FALLBACK 定位：离线增强，不进实时链。
- [x] crawler、cleaner、Docling 之间的正式生产数据契约；
- [x] 复杂文档路由与离线 worker adapter；
- [x] Docling 结果校验、canonical artifact 选择和自动回退；
- [x] 增强解析 provenance 合并到主项目 manifest/知识库；
- [x] 51 份去重真实复杂附件技术灰度；
- [x] 2 份图片型 DOCX 逐页可视化及低信息输出自动回退；
- [x] 22 个 VML 警告输出全量静态审计；
- [x] 真实 pgvector 全量 222 份入库、查询与幂等复验；
- [x] Policy Pipeline V1.0 整合验收报告。

## 5. 非阻塞外部事项

- [ ] 部署时通过未入库的 Secret 注入百炼 Key 和匹配 PostgreSQL 的数据库凭据；
- [ ] 由用户决定是否恢复接手前已删除、但旧验收测试仍要求的历史报告。

## 6. 当前真实状态

2026-07-26 已验收的数据基线：

- 357 个原始政策页面；
- 222 条可检索纯正文；
- 68 条含截止日期；
- 134 条含资金属性；
- 0 条清洗失败。

当前默认可以在不依赖数据库和 embedding key 的情况下使用 local snapshot 模式。
pgvector 的代码、表、HNSW 索引、222 份政策/3,361 个分块的真实百炼向量入库、
查询及 222 条 unchanged 幂等复验均已验证。
上述数量来自特定快照，不得硬编码。

## 7. 冻结架构摘要

```text
控制流：
User -> FastAPI -> Supervisor -> Policy Agent -> Supervisor -> User

数据访问流：
Policy Agent -> Tool Gateway -> KnowledgeTool -> PolicyRetriever
             -> local snapshot or PostgreSQL/pgvector

离线数据流：
Government -> Crawl4AI -> raw snapshot -> baseline clean
           -> optional Docling enhancement -> canonical artifact
           -> catalog / existing policy tables
```

不可改变：

- Supervisor 七节点；
- `execute_business_agent(agent_name, task, state)`；
- Agent 不直连数据资源；
- 在线查询不实时爬取、不运行 Docling；
- 既有政策表边界；
- Docling 失败回退基线；
- 不伪造数据、不使用 mock embedding 冒充完成。

## 8. 当前执行目标

完成：

```text
gz-policy-crawler
        |
logical policy_raw / versioned snapshot
        |
baseline cleaner + Docling offline enhancement
        |
Policy Knowledge Base
        |
Tool Gateway
        |
Policy Agent
        |
Supervisor
```

其中 `policy_raw` 是文件/manifest 逻辑层，不是要求新增数据库表。

详细范围和验收标准见：

`D:\industrial-park-v1.1\docs\engineering\Policy_Pipeline_Integration_Task.md`

## 9. 下一阶段

在 Policy Intelligence Pipeline V1.0 完成并通过验收后，下一阶段才是：

```text
Enterprise Intelligence Agent / 企业智能数据增强
```

不要把企业数据补全、招商漏斗、OCR 或其他 Agent 重构混入当前整合任务。

## 10. 接手工作规则

1. 先只读检查分支、脏工作区、配置、数据和测试；
2. 不运行 `git reset --hard`、`git clean` 或覆盖式 checkout；
3. 不修改或泄露 `.env`、`.env.production`、API Key；
4. 非 trivial 变更先写设计；
5. 每次变更都给出影响文件、验证命令和实际结果；
6. 外部依赖缺失时保留可运行降级路径，明确报告阻塞；
7. 没有验收证据的能力不得标记为完成。

## 11. Policy Pipeline 执行状态（2026-07-29）

当前状态：`COMPLETE`（Policy Pipeline 工程验收）。

已完成并验证：

- snapshot 到既有 Docling worker 的离线 adapter/CLI；
- 路由、校验、canonical artifact、manifest provenance 与自动回退；
- local catalog 消费 selected artifact；
- ingestion chunk provenance；
- 真实复杂 DOCX success 并选择 canonical；
- 真实 93 页 PDF partial 并回退 baseline；
- 51 份去重官方复杂附件完成真实 worker 灰度，51/51 technical success；
- 31 份 legacy `.doc` 的 WSLENV/Word COM 路径问题已修复；
- 10 个真实来源页 canonical 分组合并及 local catalog 消费通过；
- 2 份图片型 DOCX 已逐页可视化，低信息增强结果改为自动回退 baseline；
- 22 个 VML 警告输出已完成全量静态审计，未发现阻塞性低信息输出；
- Docker/PostgreSQL/pgvector 基础设施已恢复并核验；
- DashScope `text-embedding-v4@1536` 全量入库 222 份政策、3,361 个分块，0 失败；
- 同一快照复跑为 222 unchanged、0 新分块，真实 pgvector 查询返回来源证据；
- 政策专项测试 41 passed，crawler 22 passed，最新完整后端 103 passed；
- local 与 pgvector 的 readiness、HTTP 搜索、Policy Agent、trace 和运行时落库
  均已实测；pgvector Agent 未发生 mock fallback。

非阻塞外部事项：

- 生产部署时通过未入库的 Secret 注入百炼 Key 和匹配 PostgreSQL 的数据库凭据；
- 一个接手前已删除历史文档导致旧验收用例仍有 1 个既有失败。

详细证据：

`D:\industrial-park-v1.1\docs\engineering\Policy_Pipeline_Integration_Report_V1.0.md`
