"""EventBus — P3 内存事件发布/订阅总线

设计原则:
  - 基于 asyncio.Queue 的内存实现 (无外部依赖)
  - 每个 task_id 独立 channel (create_channel / close_channel)
  - TTL 自动清理: channel 无订阅者且超时未访问 → 自动关闭
  - publish() 使用 put_nowait()，不阻塞调用方

约束:
  - 仅通过 publish() 发送事件，不直接访问数据库
  - 不放入 langgraph 目录，独立 runtime 层"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认 TTL: channel 无订阅者后 300 秒自动清理
DEFAULT_CHANNEL_TTL = 300


class EventChannel:
    """单个 task_id 的事件通道"""

    def __init__(self, task_id: str, ttl: int = DEFAULT_CHANNEL_TTL):
        self.task_id = task_id
        self.queues: List[asyncio.Queue] = []
        self.created_at = time.time()
        self.last_activity = time.time()
        self.ttl = ttl
        self._closed = False

    @property
    def subscriber_count(self) -> int:
        return len(self.queues)

    @property
    def expired(self) -> bool:
        return (len(self.queues) == 0 and
                (time.time() - self.last_activity) > self.ttl)

    async def subscribe(self, queue: asyncio.Queue) -> None:
        self.queues.append(queue)
        self.last_activity = time.time()

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self.queues:
            self.queues.remove(queue)
        self.last_activity = time.time()

    async def publish(self, event: dict) -> None:
        """向所有订阅者广播事件 (非阻塞)"""
        self.last_activity = time.time()
        for q in self.queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "[EventBus] Queue full for channel=%s, dropping event",
                    self.task_id,
                )

    async def close(self) -> None:
        """关闭 channel，清理所有队列"""
        self._closed = True
        for q in self.queues:
            try:
                q.put_nowait(None)  # 发送终止信号
            except (asyncio.QueueFull, Exception):
                pass
        self.queues.clear()


class EventBus:
    """全局事件总线"""

    def __init__(self, channel_ttl: int = DEFAULT_CHANNEL_TTL):
        self._channels: Dict[str, EventChannel] = {}
        self._channel_ttl = channel_ttl
        self._cleanup_task: Optional[asyncio.Task] = None

    # ── Channel Management ──

    async def create_channel(self, task_id: str) -> EventChannel:
        """创建或获取 channel"""
        if task_id not in self._channels:
            self._channels[task_id] = EventChannel(task_id, self._channel_ttl)
            logger.debug("[EventBus] Channel created: %s", task_id)
        else:
            logger.debug("[EventBus] Channel exists: %s", task_id)
        self._ensure_cleanup()
        return self._channels[task_id]

    async def close_channel(self, task_id: str) -> None:
        """关闭并清理 channel"""
        channel = self._channels.pop(task_id, None)
        if channel:
            await channel.close()
            logger.debug("[EventBus] Channel closed: %s", task_id)

    async def get_channel(self, task_id: str) -> Optional[EventChannel]:
        """获取 channel (不创建)"""
        return self._channels.get(task_id)

    # ── Subscribe / Unsubscribe ──

    async def subscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        channel = await self.create_channel(task_id)
        await channel.subscribe(queue)

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        channel = self._channels.get(task_id)
        if channel:
            await channel.unsubscribe(queue)

    # ── Publish ──

    async def publish(self, task_id: str, event_type: str, payload: dict,
                      source: str = "supervisor") -> None:
        """发布标准化事件"""
        channel = self._channels.get(task_id)
        if channel is None:
            logger.debug("[EventBus] No channel for %s, discarding event %s", task_id, event_type)
            return

        event = {
            "event_id": str(uuid.uuid4()),
            "task_id": task_id,
            "event_type": event_type,
            "source": source,
            "timestamp": time.time(),
            "payload": payload,
        }
        await channel.publish(event)

    # ── TTL Cleanup ──

    def _ensure_cleanup(self) -> None:
        """确保清理任务在运行"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.ensure_future(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """TTL 过期 channel 清理 (每 60 秒检查一次)"""
        while True:
            await asyncio.sleep(60)
            expired = [
                tid for tid, ch in self._channels.items()
                if ch.expired
            ]
            for tid in expired:
                await self.close_channel(tid)
            if expired:
                logger.info("[EventBus] TTL cleanup: %d channels removed", len(expired))

    # ── Stats ──

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    @property
    def total_subscribers(self) -> int:
        return sum(ch.subscriber_count for ch in self._channels.values())


# 全局单例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
