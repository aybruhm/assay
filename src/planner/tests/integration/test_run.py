from datetime import date
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from planner.agent.adapters.fake import ScriptedModel
from planner.agent.models import AgentDecision, ProfileExtraction, ToolCall
from planner.graph.nodes.llm import agent as agent_module
from planner.graph.nodes.llm import intake as intake_module
from planner.graph.runtime import compiled, config
from planner.graph.state import PlanState, Profile


async def test_full_run_with_fake_model(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            PlanState(
                messages=[HumanMessage(content="I earn 45,000 a year in England")],
                profile=Profile(planning_date=date(2026, 10, 1)),
            ),
            config(str(uuid4())),
        )
    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    assert out["report"].citations
    result = out["results"][0]
    assert result.get("net_pay") == 359_196_000


async def test_run_pauses_for_missing_fields_and_resumes(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    thread_id = str(uuid4())

    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            PlanState(
                messages=[HumanMessage(content="hello")],
                profile=Profile(planning_date=date(2026, 10, 1)),
            ),
            config(thread_id),
        )

    # The run paused: an interrupt asks for exactly the missing field.
    assert out["missing"] == ["gross_annual"]
    interrupt = out["__interrupt__"][0]
    assert interrupt.value == {
        "kind": "input",
        "fields": ["gross_annual"],
        "message": "What is your gross annual income?",
    }

    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            Command(resume="I earn 45,000 and I am not Scottish"),
            config(thread_id),
        )

    assert out["validation"].status == "passed"
    assert out["results"][0].get("net_pay") == 359_196_000


async def test_second_run_replaces_results(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    thread_id = str(uuid4())
    async with compiled(db_url) as graph:
        first = await graph.ainvoke(
            PlanState(
                messages=[HumanMessage(content="I earn 45,000 a year in England")],
                profile=Profile(planning_date=date(2026, 10, 1)),
            ),
            config(thread_id),
        )
        second = await graph.ainvoke(
            PlanState(
                messages=[HumanMessage(content="What is my net pay?")],
                profile=first["profile"],
            ),
            config(thread_id),
        )
    assert len(first["results"]) == 1
    assert len(second["results"]) == 1


async def test_pension_run_uses_the_pension_calculator(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = ScriptedModel(
        extractions=[
            ProfileExtraction(
                country="GB",
                gross_annual="85,000",
                scottish_taxpayer=False,
                pension_rate="0.06",
            )
        ],
        decisions=[
            AgentDecision(
                action="call_tools",
                tool_calls=[ToolCall(name="pension", arguments={})],
            )
        ],
    )
    monkeypatch.setattr(intake_module, "model", lambda: fake)
    monkeypatch.setattr(agent_module, "model", lambda: fake)
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            PlanState(
                messages=[
                    HumanMessage(content="I earn 85,000 and pay 6% into my pension")
                ],
                profile=Profile(planning_date=date(2026, 10, 18)),
            ),
            config(str(uuid4())),
        )
    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    result = out["results"][0]
    assert result.calculator == "gb.pension"
    assert result.get("pension_contribution") == 51_000_000
    assert result.get("net_pay") == 568_994_000


async def test_director_pay_run_uses_the_director_calculator(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = ScriptedModel(
        extractions=[
            ProfileExtraction(
                country="GB",
                company_profit="100,000",
                director_salary="12,570",
                scottish_taxpayer=False,
            )
        ],
        decisions=[
            AgentDecision(
                action="call_tools",
                tool_calls=[ToolCall(name="director_pay", arguments={})],
            )
        ],
    )
    monkeypatch.setattr(intake_module, "model", lambda: fake)
    monkeypatch.setattr(agent_module, "model", lambda: fake)
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            PlanState(
                messages=[
                    HumanMessage(
                        content=(
                            "I have a limited company with 100,000 profit "
                            "and take a 12,570 salary"
                        )
                    )
                ],
                profile=Profile(planning_date=date(2026, 10, 18)),
            ),
            config(str(uuid4())),
        )
    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    result = out["results"][0]
    assert result.calculator == "gb.director_pay"
    assert result.get("net_pay") == 652_096_239


async def test_isa_run_uses_the_isa_calculator(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = ScriptedModel(
        extractions=[
            ProfileExtraction(
                country="GB",
                gross_annual="20,000",
                savings_amount="10,000",
                annual_growth_rate="5%",
                investment_years="10 years",
            )
        ],
        decisions=[
            AgentDecision(
                action="call_tools",
                tool_calls=[ToolCall(name="isa_vs_general", arguments={})],
            )
        ],
    )
    monkeypatch.setattr(intake_module, "model", lambda: fake)
    monkeypatch.setattr(agent_module, "model", lambda: fake)
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            PlanState(
                messages=[
                    HumanMessage(
                        content=(
                            "I have 10,000 to invest for 10 years at 5% a year. "
                            "How does an ISA compare with a general account?"
                        )
                    )
                ],
                profile=Profile(planning_date=date(2026, 10, 18)),
            ),
            config(str(uuid4())),
        )
    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    result = out["results"][0]
    assert result.calculator == "gb.isa_vs_general"
    assert result.get("difference") == 5_920_103


async def test_dividend_capacity_run_uses_the_dividend_calculator(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = ScriptedModel(
        extractions=[
            ProfileExtraction(
                country="GB",
                gross_annual="85,000",
                company_profit="100,000",
                distributable_reserves="0",
                scottish_taxpayer=False,
            )
        ],
        decisions=[
            AgentDecision(
                action="call_tools",
                tool_calls=[ToolCall(name="dividend_capacity", arguments={})],
            )
        ],
    )
    monkeypatch.setattr(intake_module, "model", lambda: fake)
    monkeypatch.setattr(agent_module, "model", lambda: fake)
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    async with compiled(db_url) as graph:
        out = await graph.ainvoke(
            PlanState(
                messages=[
                    HumanMessage(
                        content=(
                            "I earn 85,000 from PAYE. My company makes 100,000 "
                            "profit and has no reserves. How much can I take "
                            "as dividends?"
                        )
                    )
                ],
                profile=Profile(planning_date=date(2026, 10, 18)),
            ),
            config(str(uuid4())),
        )
    assert out.get("failure") is None
    assert out["validation"].status == "passed"
    result = out["results"][0]
    assert result.calculator == "gb.dividend_capacity"
    assert result.get("available_dividend") == 772_500_000
    assert result.get("dividend_tax") == 287_740_850
