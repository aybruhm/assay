from datetime import date

from langchain_core.messages import HumanMessage

from planner.audit.sink import InMemorySink
from planner.core.types import CalcLine, CalcResult
from planner.graph.nodes.control import finish
from planner.graph.state import (
    Citation,
    PlanState,
    Profile,
    Report,
    Validation,
)
from planner.rules.schema import RulePackRef

CONFIG = {"configurable": {"thread_id": "t-1"}}


def _delivered_state() -> PlanState:
    return PlanState(
        messages=[HumanMessage(content="hi")],
        profile=Profile(
            country="GB",
            planning_date=date(2026, 10, 1),
            gross_annual=450_000_000,
            scottish_taxpayer=False,
        ),
        rule_pack=RulePackRef(jurisdiction="GB", tax_year="2026-27", version=1),
        results=[
            CalcResult(
                result_id="9f2c1a3b4d5e",
                calculator="gb.take_home",
                calculator_version="1",
                inputs={"gross_annual": 450_000_000, "scottish_taxpayer": False},
                lines=[
                    CalcLine(
                        key="net_pay",
                        amount=346_224_000,
                        rule_ids=["gb.income_tax.basic_rate"],
                    )
                ],
            )
        ],
        report=Report(
            text="Your net pay is £34,622.40 [r:9f2c1a3b4d5e.net_pay].",
            citations=[
                Citation(result_id="9f2c1a3b4d5e", key="net_pay", shown="£34,622.40")
            ],
        ),
        validation_log=[Validation(status="passed", attempts=1, mismatches=[])],
    )


def test_deliver_records_audit(monkeypatch):
    recorded = InMemorySink()
    monkeypatch.setattr(finish, "sink", lambda: recorded)
    out = finish.deliver(_delivered_state(), CONFIG)  # type: ignore[arg-type]
    assert out == {}
    assert [key for events, key in recorded.batches] == ["t-1:delivery"]
    kinds = [event.kind for events, _ in recorded.batches for event in events]
    assert kinds == ["rule_pack_loaded", "calculation", "validation", "delivery"]


def test_audit_failure_blocks_delivery(monkeypatch):
    monkeypatch.setattr(finish, "sink", lambda: InMemorySink(fail=True))
    out = finish.deliver(_delivered_state(), CONFIG)  # type: ignore[arg-type]
    assert out == {"failure": "audit write failed: injected failure"}
