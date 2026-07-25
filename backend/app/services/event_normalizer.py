"""EventNormalizer — P3 统一事件格式转换器

职责:
  - 将 Supervisor/Agent 原始事件 → 标准化 StreamEvent 格式
  - 所有 SSE 输出事件必须经过此 normalizer
  - 统一格式: { event_id, task_id, event_type, source, timestamp, payload }

约束:
  - 不放 langgraph 目录
  - 不访问数据库
  - 不访问网络"""

from enum import Enum
from typing import Dict, Any


class StreamEventType(str, Enum):
    """前端唯一消费的 event name"""
    NODE_START    = "node_start"
    NODE_COMPLETE = "node_complete"
    AGENT_START   = "agent_start"
    AGENT_DONE    = "agent_done"
    AGENT_ERROR   = "agent_error"
    LLM_TOKEN     = "llm_token"
    DONE          = "done"
    ERROR         = "error"
    SNAPSHOT      = "snapshot"
    HEARTBEAT     = "heartbeat"


# 原始事件类型 → 标准事件类型映射
TYPE_MAP: Dict[str, StreamEventType] = {
    "supervisor_node":   StreamEventType.NODE_COMPLETE,
    "agent_start":       StreamEventType.AGENT_START,
    "agent_complete":    StreamEventType.AGENT_DONE,
    "agent_error":       StreamEventType.AGENT_ERROR,
    "llm_token":         StreamEventType.LLM_TOKEN,
    "done":              StreamEventType.DONE,
    "error":             StreamEventType.ERROR,
    "snapshot":          StreamEventType.SNAPSHOT,
    "heartbeat":         StreamEventType.HEARTBEAT,
}


class EventNormalizer:
    """标准化事件转换器

    输入: 原始事件 dict (来自 EventBus 或 LangGraph astream_events)
      {
        "event_id": "...",
        "task_id": "...",
        "event_type": "supervisor_node",  # 原始类型
        "source": "supervisor",
        "timestamp": 1234567890.0,
        "payload": { "node": "intent_recognition", ... }
      }

    输出: 标准化 StreamEvent
      {
        "event_id": "...",
        "task_id": "...",
        "event_type": "node_complete",     # 标准化类型
        "source": "supervisor",
        "timestamp": 1234567890.0,
        "payload": { "node": "intent_recognition", ... }
      }
    """

    @staticmethod
    def normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
        """将原始事件转换为标准格式"""
        event_type = TYPE_MAP.get(raw.get("event_type"), StreamEventType.HEARTBEAT)

        return {
            "event_id":   raw.get("event_id", ""),
            "task_id":    raw.get("task_id", ""),
            "event_type": event_type.value,
            "source":     raw.get("source", "unknown"),
            "timestamp":  raw.get("timestamp", 0),
            "payload":    raw.get("payload", {}),
        }

    @staticmethod
    def normalize_batch(raw_events: list) -> list:
        """批量标准化"""
        return [EventNormalizer.normalize(e) for e in raw_events]
