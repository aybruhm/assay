from datetime import date
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage

from planner.agent.adapters.fake import ScriptedModel
from planner.agent.models import AgentDecision, ProfileExtraction, ToolCall
from planner.graph.nodes.llm import agent as agent_module
from planner.graph.nodes.llm import intake as intake_module
from planner.graph.runtime import compiled, config
from planner.graph.state import PlanState, Profile


def _start_input() -> PlanState:
    return PlanState(
        messages=[HumanMessage(content="I earn 25 million naira a year")],
        profile=Profile(planning_date=date(2026, 7, 15)),
    )


async def test_ng_run_end_to_end(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = ScriptedModel(
        extractions=[ProfileExtraction(country="NG", gross_annual="25,000,000")],
        decisions=[
            AgentDecision(
                action="call_tools",
                tool_calls=[ToolCall(name="take_home", arguments={})],
            )
        ],
    )
    monkeypatch.setattr(intake_module, "model", lambda: fake)
    monkeypatch.setattr(agent_module, "model", lambda: fake)
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")

    async with compiled(db_url) as graph:
        out = await graph.ainvoke(_start_input(), config(str(uuid4())))

    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    result = out["results"][0]
    assert result.calculator == "ng.take_home"
    # Rent is 0 on the graph path: taxable 23,000,000 -> tax 4,260,000.
    assert result.get("income_tax") == 42_600_000_000
    assert result.get("net_pay") == 187_400_000_000
    # The narration carries naira figures with citations.
    assert "₦" in out["report"].text
    assert "[r:" in out["report"].text
    assert out["report"].citations
