import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from planner.graph.state import PlanState

Kind = Literal[
    "rule_pack_loaded",
    "research",
    "calculation",
    "validation",
    "approval",
    "delivery",
]


class AuditEvent(BaseModel):
    kind: Kind
    thread_id: str
    at: datetime
    data: dict[str, str | int | bool | list[str]]


def _hash(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()


def audit_events(state: PlanState, thread_id: str) -> list[AuditEvent]:
    """
    Build the audit events for a finished run.

    Args:
        state: The completed run state.
        thread_id: The thread the events belong to.

    Returns:
        The rule pack, calculation, validation, approval, and delivery
        events.
    """
    now = datetime.now(UTC)

    def make_event(kind: Kind, **data: str | int | bool | list[str]) -> AuditEvent:
        return AuditEvent(kind=kind, thread_id=thread_id, at=now, data=data)

    assert state.rule_pack is not None and state.report is not None
    events = [
        make_event(
            "rule_pack_loaded",
            jurisdiction=state.rule_pack.jurisdiction,
            tax_year=state.rule_pack.tax_year,
            version=state.rule_pack.version,
        )
    ]
    for item in sorted(state.research, key=lambda item: item.research_id):
        events.append(
            make_event(
                "research",
                research_id=item.research_id,
                source_kind=item.kind,
                title=item.title,
                url=item.url,
                fetched_at=item.fetched_at.isoformat(),
            )
        )
    for result in sorted(state.results, key=lambda result: result.result_id):
        events.append(
            make_event(
                "calculation",
                result_id=result.result_id,
                calculator=result.calculator,
                calculator_version=result.calculator_version,
                input_hash=_hash(result.inputs),
                rule_ids=sorted(
                    {rule_id for line in result.lines for rule_id in line.rule_ids}
                ),
            )
        )
    for attempt, validation_entry in enumerate(state.validation_log, start=1):
        events.append(
            make_event(
                "validation",
                attempt=attempt,
                status=validation_entry.status,
                mismatches=validation_entry.mismatches,
            )
        )
    if state.approval is not None:
        events.append(
            make_event(
                "approval",
                reviewer=state.approval.reviewer,
                approved=state.approval.approved,
                note=state.approval.note,
            )
        )
    events.append(
        make_event(
            "delivery",
            report_hash=_hash(state.report.text),
            cited=sorted({citation.result_id for citation in state.report.citations}),
            sources=sorted({item.url for item in state.research}),
        )
    )
    return events
