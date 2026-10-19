from datetime import date
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from planner.agent.adapters.fake import ScriptedModel
from planner.agent.models import AgentDecision, ProfileExtraction, ToolCall
from planner.audit.sink import InMemorySink
from planner.graph.nodes.control import finish
from planner.graph.nodes.llm import agent as agent_module
from planner.graph.nodes.llm import intake as intake_module
from planner.graph.runtime import compiled, config
from planner.graph.state import PlanState, Profile


def _start_input() -> PlanState:
    return PlanState(
        messages=[HumanMessage(content="I earn 45,000 a year in England")],
        profile=Profile(planning_date=date(2026, 10, 1)),
    )


async def test_audit_failure_ends_the_run_without_delivery(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setattr(finish, "sink", lambda: InMemorySink(fail=True))
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(_start_input(), config(str(uuid4())))
    assert out["validation"].status == "passed"  # figures were fine
    assert "audit write failed" in out["failure"]
    assert out["report"] is None  # nothing delivered


async def test_healthy_audit_delivers(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = InMemorySink()
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setattr(finish, "sink", lambda: recorded)
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(_start_input(), config(str(uuid4())))
    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    assert out["report"] is not None
    assert recorded.batches
    kinds = [event.kind for events, _ in recorded.batches for event in events]
    assert kinds == ["rule_pack_loaded", "calculation", "validation", "delivery"]


async def test_interrupt_path_still_delivers_audit(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = InMemorySink()
    fake = ScriptedModel(
        extractions=[ProfileExtraction(country="GB")],
        decisions=[
            AgentDecision(
                action="ask",
                fields=["gross_annual"],
                message="What is your gross annual income?",
            ),
            AgentDecision(
                action="call_tools",
                tool_calls=[
                    ToolCall(
                        name="take_home",
                        arguments={
                            "gross_annual": "45,000",
                            "scottish_taxpayer": False,
                        },
                    )
                ],
            ),
        ],
    )
    monkeypatch.setattr(intake_module, "model", lambda: fake)
    monkeypatch.setattr(agent_module, "model", lambda: fake)
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setattr(finish, "sink", lambda: recorded)
    thread_id = str(uuid4())
    async with compiled(db_url) as graph:
        await graph.ainvoke(_start_input(), config(thread_id))
        out = await graph.ainvoke(Command(resume="45,000 and no"), config(thread_id))
    assert out["validation"].status == "passed"
    assert recorded.batches
