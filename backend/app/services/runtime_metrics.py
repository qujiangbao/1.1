"""Process-local agent execution metrics.

The database remains the durable source of completed execution history. This
registry supplies the current running state and real metrics when PostgreSQL is
intentionally disabled.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any


class RuntimeMetrics:
    def __init__(self, max_events: int = 10_000) -> None:
        self._lock = RLock()
        self._active: dict[str, dict[str, Any]] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)

    def begin(self, agent_name: str, task_id: str) -> float:
        started = perf_counter()
        with self._lock:
            self._active[agent_name] = {
                "task_id": task_id,
                "started": started,
                "started_at": datetime.now(timezone.utc),
            }
        return started

    def finish(
        self,
        agent_name: str,
        task_id: str,
        status: str,
        started: float,
        duration_ms: int = 0,
    ) -> None:
        measured_ms = max(1, int((perf_counter() - started) * 1000))
        event = {
            "agent_name": agent_name,
            "task_id": task_id,
            "status": status,
            "duration_ms": max(int(duration_ms or 0), measured_ms),
            "completed_at": datetime.now(timezone.utc),
        }
        with self._lock:
            active = self._active.get(agent_name)
            if active and active.get("task_id") == task_id:
                self._active.pop(agent_name, None)
            self._events.append(event)

    def snapshot(self) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date()
        with self._lock:
            active = {name: dict(value) for name, value in self._active.items()}
            events = [
                dict(event)
                for event in self._events
                if event["completed_at"].date() == today
            ]
        return {"active": active, "events": events}

    def reset_for_tests(self) -> None:
        with self._lock:
            self._active.clear()
            self._events.clear()


_runtime_metrics = RuntimeMetrics()


def get_runtime_metrics() -> RuntimeMetrics:
    return _runtime_metrics
