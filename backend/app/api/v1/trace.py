"""Trace API — 从 LangGraph Checkpointer 检索真实执行链路 (P2: async graph)"""
from fastapi import APIRouter
from app.schemas.agent import TraceResponse
from app.langgraph.graph import get_supervisor_graph
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/agent/task/{task_id}/trace", response_model=TraceResponse)
async def get_trace(task_id: str):
    """从 LangGraph checkpointer 检索真实 trace_steps 和 task_plan"""
    try:
        # P2: async initialization
        graph = await get_supervisor_graph()
        config = {"configurable": {"thread_id": task_id}}
        state = graph.get_state(config)

        if state is None or not state.values:
            return _fallback_trace(task_id, "no_state_found")

        sv = state.values
        trace_steps = sv.get("trace_steps", [])
        task_plan = sv.get("task_plan", [])
        agent_results = sv.get("agent_results", {})

        nodes = [{"id": "supervisor", "label": "Supervisor", "type": "supervisor"}]
        for agent_name, ar in agent_results.items():
            nodes.append({
                "id": agent_name.lower(),
                "label": agent_name,
                "type": "agent",
                "status": ar.get("status", "unknown"),
                "result": _truncate(ar.get("result", {}).get("summary", ""), 100),
                "execution_time_ms": ar.get("execution_time_ms", 0),
            })

        edges = []
        prev_agent = "supervisor"
        for task in task_plan:
            agent_id = task.get("agent", "").lower()
            if agent_id:
                edges.append({"from": prev_agent, "to": agent_id})
                prev_agent = agent_id

        steps = []
        for ts in trace_steps:
            steps.append({
                "step": ts.get("step", 0),
                "type": ts.get("type", ""),
                "agent": ts.get("agent", ""),
                "action": ts.get("action", ""),
                "input": ts.get("input", {}),
                "output": ts.get("output", {}),
                "timestamp": ts.get("timestamp", ""),
                "duration_ms": ts.get("duration_ms", 0),
            })

        plan_summary = []
        for t in task_plan:
            plan_summary.append({
                "task_id": t.get("task_id", ""),
                "agent": t.get("agent", ""),
                "intent": t.get("intent", ""),
                "status": t.get("status", ""),
                "dependencies": t.get("dependencies", []),
            })

        return TraceResponse(
            trace_id=f"TRACE-{task_id}",
            task_id=task_id,
            status=sv.get("status", "completed"),
            started_at=sv.get("started_at", ""),
            completed_at=sv.get("completed_at", ""),
            execution_time_ms=_calc_duration(trace_steps),
            steps=steps if steps else _minimal_steps(agent_results),
            nodes=nodes if len(nodes) > 1 else _minimal_nodes(agent_results, task_plan),
            edges=edges if edges else _minimal_edges(agent_results),
            task_plan=plan_summary,
        )

    except Exception as e:
        logger.warning(f"Trace retrieval failed for {task_id}: {e}")
        return _fallback_trace(task_id, str(e))


def _fallback_trace(task_id: str, reason: str) -> TraceResponse:
    return TraceResponse(
        trace_id=f"TRACE-{task_id}",
        task_id=task_id,
        status="completed",
        started_at="",
        completed_at="",
        execution_time_ms=0,
        steps=[{
            "step": 1, "type": "supervisor_decision", "agent": "Supervisor",
            "action": "trace_retrieval", "input": {"task_id": task_id},
            "output": {"note": f"Trace state unavailable ({reason}). Run a new chat to generate traces."},
            "timestamp": "", "duration_ms": 0,
        }],
        nodes=[{"id": "supervisor", "label": "Supervisor", "type": "supervisor"}],
        edges=[],
    )


def _minimal_steps(agent_results: dict) -> list:
    steps = []
    for i, (name, ar) in enumerate(agent_results.items()):
        steps.append({
            "step": i + 1,
            "type": "agent_call",
            "agent": name,
            "action": ar.get("result", {}).get("summary", "")[:80],
            "input": {},
            "output": {"status": ar.get("status")},
            "timestamp": "",
            "duration_ms": ar.get("execution_time_ms", 0),
        })
    return steps


def _minimal_nodes(agent_results: dict, task_plan: list) -> list:
    nodes = [{"id": "supervisor", "label": "Supervisor", "type": "supervisor"}]
    seen = {"supervisor"}
    for task in task_plan:
        agent = task.get("agent", "")
        aid = agent.lower()
        if aid not in seen:
            nodes.append({"id": aid, "label": agent, "type": "agent"})
            seen.add(aid)
    for name in agent_results:
        aid = name.lower()
        if aid not in seen:
            nodes.append({"id": aid, "label": name, "type": "agent"})
            seen.add(aid)
    return nodes


def _minimal_edges(agent_results: dict) -> list:
    edges = []
    prev = "supervisor"
    for name in agent_results:
        edges.append({"from": prev, "to": name.lower()})
        prev = name.lower()
    return edges


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def _calc_duration(steps: list) -> int:
    return sum(s.get("duration_ms", 0) for s in steps)
