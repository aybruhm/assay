from typing import Any

from langchain_core.runnables import RunnableConfig

from planner.audit.events import audit_events
from planner.audit.sink import AuditError, sink
from planner.graph.state import PlanState


def deliver(state: PlanState, config: RunnableConfig) -> dict[str, Any]:
    thread_id = str((config.get("configurable") or {})["thread_id"])
    try:
        sink().record_batch(
            audit_events(state, thread_id),
            idempotency_key=f"{thread_id}:delivery",
        )
    except AuditError as exc:
        return {"failure": f"audit write failed: {exc}"}
    return {}


def fail_closed(state: PlanState) -> dict[str, Any]:
    reason = (
        state.failure or "; ".join(state.validation.mismatches) or "validation failed"
    )
    return {"report": None, "failure": reason}
