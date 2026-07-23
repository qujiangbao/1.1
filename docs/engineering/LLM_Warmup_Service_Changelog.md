# LLM Warmup Service — 变更日志

> 日期：2026-07-22 | 版本：1.0.0 | 类型：基础设施增强

---

## 变更概述

解决比赛中最关键的性能问题：Agent Chat 冷启动 55 秒。

新增 LLM Warmup Service，后端启动后自动发送轻量测试请求预热 DeepSeek API 连接池。

---

## 变更文件

| 文件 | 操作 | 说明 |
|------|:---:|------|
| `backend/app/core/llm_warmup.py` | 新增 | Warmup 核心服务 |
| `backend/app/api/v1/health.py` | 修改 | 新增 `/health/warmup` 端点 |
| `backend/app/main.py` | 修改 | lifespan 中集成 warmup 启动 |

---

## 新增端点

```
GET /api/v1/health/warmup
```

**响应示例（预热完成）：**
```json
{
    "status": "ready",
    "llm_ready": true,
    "warmup_state": "ready",
    "warmup_time_ms": 21204,
    "model": "deepseek-chat",
    "error": null
}
```

**状态机：**
```
pending → warming_up → ready   ✅
                      → failed  ⚠️ (仍可正常使用，首次请求会慢)
```

---

## 效果验证

| 测试 | 预热前 | 预热后 | 提升 |
|------|:---:|:---:|:---:|
| Agent Chat 首次调用 | 55.3s | 12.0s | **4.6x** |
| Warmup 耗时 | — | 21.2s（后台，不阻塞） | — |

---

## 比赛日流程变更

```
旧流程：
  T-10min  手动发一次 Agent Chat 预热（容易忘）

新流程：
  后端启动 → 自动预热 → /health/warmup 返回 ready
  T-5min   调用 /health/warmup 确认 llm_ready:true
  → 无需手动预热！
```

---

## 设计原则

- **不阻塞启动**：Warmup 通过 `asyncio.create_task` 后台运行，后端立即可用
- **优雅降级**：Warmup 失败不影响系统功能，仅记录 warning
- **最小 Token**：预热用 `prompt="OK"` + `max_tokens=10`，成本接近零
