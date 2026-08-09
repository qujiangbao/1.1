# Industrial Park Agent — 文档索引

> 生成日期：2026-07-28 | 版本：V1.3

---

## 文档导航

### 架构冻结层（docs/architecture/）
唯一事实来源，设计规范，非经 PR 不得修改。

| 文档 | 说明 | 版本 |
|------|------|:---:|
| ARCHITECTURE.md | 架构全景（FROZEN） | V1.3 |
| System_Architecture_V1.0.md | Policy Pipeline 整合架构入口（FROZEN） | V1.0 |
| Agent_Communication_Contract_V1.0.md | Agent 通信协议 | V1.0 |
| Unified_API_Contract_V1.0.md | 统一 API 契约 | V1.0 |
| Tool_Gateway_Design_V1.0.md | 工具网关设计 | V1.0 |
| Supervisor_Technical_Design_V1.1.md | Supervisor 技术设计 | V1.1 |
| Database_Physical_Schema_V1.0.md | 数据库物理 Schema | V1.0 |
| FastAPI_Engineering_Design_V1.0.md | FastAPI 工程设计 | V1.0 |
| React_Frontend_Architecture_V1.0.md | React 前端架构 | V1.0 |
| Revision_V2.0_FINAL.md | ChatGPT 审核修订 V2.0 | V2.0 |

### Agent 设计层（docs/agents/）
各业务 Agent 的详细工作流与设计。

| 文档 | Agent | 版本 |
|------|-------|:---:|
| Industry_Agent_Technical_Design_V1.0.md | 产业分析 Agent | V1.0 |
| Investment_Agent_Workflow_V1.0.md | 招商 Agent | V1.0 |
| Risk_Agent_Workflow_V1.0.md | 风险预警 Agent | V1.0 |
| Policy_RAG_Workflow_V1.0.md | 政策 RAG Agent | V1.0 |
| Enterprise_Service_Architecture_V1.0.md | 企业服务 Agent | V1.0 |
| BI_Agent_Architecture_V1.0.md | BI 驾驶舱 Agent | V1.0 |
| Demo_Product_Agent_Design_V1.0.md | Demo/产品设计 | V1.0 |

### 工程实施层（docs/engineering/）— 26 份
当前活跃的开发过程文档、实现报告、升级记录。

| 类别 | 关键文档 | 数量 |
|------|---------|:---:|
| **设计规划** | `01_Engineering_Readiness.md` `02_Implementation_Plan.md` `03_Code_Architecture.md` `05_Test_Plan.md` `06_Deployment_Guide.md` | 5 |
| **V1.2 升级** | `RBAC_Architecture_V1.0.md` `RBAC_Implementation_Report_V1.0.md` `P3_Streaming_*` `LangGraph_Checkpointer_*` `WebSocket_Streaming_*` | 8 |
| **V1.3 升级** | `Production_Stabilization_*` `Guangzhou_Policy_*` `Data_Activation_*` `Local_Enterprise_*` `Remaining_Optimization_*` | 7 |
| **当前整合任务** | `Policy_Pipeline_Integration_Task.md` `Policy_Pipeline_Integration_Implementation_Plan_V1.0.md` `Policy_Pipeline_Integration_Report_V1.0.md` | 3 |
| **P5/P6** | `P5_Database_Migration_Report_V1.0.md` `P6_Deployment_Report_V1.0.md` | 2 |
| **Project Handoff** | `Hermes_Project_Handoff_2026-07-26.md` `Codex_Project_Handoff_2026-07-28.md` | 2 |
| **Other** | `Frontend_Interaction_Repair_Report_V1.2.md` `LLM_Warmup_Service_Changelog.md` | 2 |

### 归档层（docs/archive/）— 40+ 份
历史版本，仅供参考，不再维护。

| 目录 | 内容 | 数量 |
|------|------|:---:|
| `v1.0-drafts/` | V1.0 中文草稿（ChatGPT 生成） | 16 |
| `v1.1-competition/` | V1.1 比赛时代文档 + Demo 脚本 + Sprint 报告 | 24 + reports/ |

### 根目录文档

| 文档 | 用途 |
|------|------|
| `POLICY_PIPELINE_EXECUTION_HANDOFF.md` | 当前 Policy Pipeline 任务的单一执行入口 |
| README.md | 项目概览 + 快速启动 |
| CODEBUDDY.md | AI 开发助手上下文（架构、约束、工作流） |
| .env.example | 开发环境变量模板 |
| .env.production.example | 生产环境变量模板 |
| docker-compose.yml | 容器编排 |
| nginx.conf | 反向代理配置 |
| deploy.sh | 部署脚本 |
| warmup.sh | LLM 预热脚本 |
| e2e-test.sh | 端到端测试 |

### AI 接手入口

| 文档 | 用途 |
|------|------|
| `docs/PROJECT_CONTEXT.md` | 所有 AI/Hermes/Codex 的当前任务入口 |
| `AI_HANDOFF.md` | 项目总体接手说明 |
| `docs/engineering/Codex_Project_Handoff_2026-07-28.md` | 工程现状与安全边界 |
| `docs/engineering/Policy_Pipeline_Integration_Task.md` | 当前整合范围、数据契约与验收标准 |

---

## 文档分类统计

| 分类 | 数量 | 说明 |
|------|:---:|------|
| 架构冻结层 | 9 | 设计规范，单点事实来源 |
| Agent 设计层 | 7 | 业务 Agent 工作流 |
| 工程实施层 | 50+ | 开发过程文档 |
| 归档层 | 16+ | 历史版本 |
| 根目录 | 10 | 项目入口 |

---

> 本文档为自动生成索引。新增文档请同步更新。
