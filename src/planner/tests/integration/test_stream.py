from datetime import date
from uuid import uuid4

from langchain_core.messages import HumanMessage

from planner.agent.adapters.fake import ScriptedModel
from planner.agent.models import ProfileExtraction
from planner.cli import _stream
from planner.graph.nodes.llm import intake as intake_module
from planner.graph.runtime import compiled, config
from planner.graph.state import PlanState, Profile


async def test_stream_reports_nodes_and_returns_the_interrupt(
    db_url, monkeypatch, capsys
):
    monkeypatch.setattr(
        intake_module,
        "model",
        lambda: ScriptedModel(extractions=[ProfileExtraction()]),
    )
    thread_id = str(uuid4())
    async with compiled(db_url) as graph:
        out = await _stream(
            graph,
            PlanState(
                messages=[HumanMessage(content="hello")],
                profile=Profile(planning_date=date(2026, 10, 18)),
            ),
            config(thread_id),
        )

    assert out["__interrupt__"][0].value["fields"] == ["country"]
    assert "[intake]" in capsys.readouterr().err
