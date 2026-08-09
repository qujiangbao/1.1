# 生产运维手册

## 备份

在项目根目录执行：

```powershell
.\scripts\backup-production.ps1
.\scripts\verify-backup.ps1 -BackupDirectory .\.local-backups\<时间戳>
```

备份包含 PostgreSQL 逻辑备份、园区资料原件/解析文本/结构化结果、政策快照和 Supervisor 检查点，并生成 SHA-256 清单。备份目录不得提交 Git，应复制到加密的异地存储。建议每日备份、保留 30 天，并每月至少做一次隔离环境恢复演练。

## 恢复

恢复会覆盖当前数据库和资料卷，必须显式确认：

```powershell
.\scripts\restore-production.ps1 -BackupDirectory .\.local-backups\<时间戳> -ConfirmRestore
.\scripts\runtime_acceptance.ps1
```

## 数据生命周期

- 园区资料删除采用可恢复归档，归档后立即退出检索、企业结构化和政策匹配。
- 政策更新保留来源 URL、正文指纹、版本和抓取记录；原文变化会使既有资格规则失效为草稿。
- 招商候选、CRM 事件、服务工单和 Agent Trace 属业务记录，不应由普通用户物理删除。
- 生产日志不得记录口令、JWT、政策爬虫授权令牌或企业联系人个人敏感信息。
- 对不再具备处理目的的数据，由园区数据负责人审批后按类别清理，并保留审批与执行记录。

## 上线监控最低要求

- 每 1 分钟检查 `/api/v1/health/ready`，连续 3 次失败告警。
- 监控容器重启次数、磁盘使用率、PostgreSQL 连接数、接口 5xx 比例和 Agent 任务失败率。
- 磁盘达到 70% 预警、85% 严重告警；数据库和资料备份失败必须立即告警。
- 公网部署必须由负载均衡或 Nginx TLS 入口提供 HTTPS；当前仓库的 8080 HTTP 仅适用于本机或内网验收。
