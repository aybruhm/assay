from datetime import UTC, date, datetime
from typing import Any, cast

from langchain_core.messages import HumanMessage

from planner.audit.events import AuditEvent, audit_events
from planner.core.types import CalcLine, CalcResult
from planner.graph.state import (
    Approval,
    Citation,
    PlanState,
    Profile,
    Report,
    Validation,
)
from planner.research.models import ResearchResult
from planner.rules.schema import RulePackRef


def _delivered_state(**overrides: object) -> PlanState:
    result = CalcResult(
        result_id="9f2c1a3b4d5e",
        calculator="gb.take_home",
        calculator_version="1",
        inputs={"gross_annual": 450_000_000, "scottish_taxpayer": False},
        lines=[
            CalcLine(
                key="net_pay",
                amount=346_224_000,
                rule_ids=["gb.income_tax.basic_rate", "gb.ni.main_rate"],
            ),
        ],
    )
    defaults = dict(
        messages=[HumanMessage(content="hi")],
        profile=Profile(
            country="GB",
            planning_date=date(2026, 10, 1),
            gross_annual=450_000_000,
            scottish_taxpayer=False,
        ),
        rule_pack=RulePackRef(jurisdiction="GB", tax_year="2026-27", version=1),
        results=[result],
        report=Report(
            text="Your net pay is £34,622.40 [r:9f2c1a3b4d5e.net_pay].",
            citations=[
                Citation(result_id="9f2c1a3b4d5e", key="net_pay", shown="£34,622.40")
            ],
        ),
        validation_log=[Validation(status="passed", attempts=1, mismatches=[])],
    )
    defaults.update(overrides)
    return PlanState(**cast(dict[str, Any], defaults))


def test_delivered_run_emits_five_event_kinds():
    state = _delivered_state(
        approval=Approval(approved=True, reviewer="reviewer-1", note="ok")
    )
    events = audit_events(state, "t-1")
    kinds = [event.kind for event in events]
    assert kinds == [
        "rule_pack_loaded",
        "calculation",
        "validation",
        "approval",
        "delivery",
    ]
    assert all(isinstance(event, AuditEvent) for event in events)
    assert all(event.thread_id == "t-1" for event in events)


def test_without_approval_the_approval_event_is_omitted():
    events = audit_events(_delivered_state(), "t-1")
    assert "approval" not in [event.kind for event in events]


def test_calculation_event_hashes_inputs_instead_of_storing_them():
    events = audit_events(_delivered_state(), "t-1")
    calculation_event = next(event for event in events if event.kind == "calculation")
    assert "input_hash" in calculation_event.data
    assert "gross_annual" not in calculation_event.data
    assert calculation_event.data["rule_ids"] == [
        "gb.income_tax.basic_rate",
        "gb.ni.main_rate",
    ]
    assert calculation_event.data["result_id"] == "9f2c1a3b4d5e"


def test_delivery_event_hashes_the_report_text():
    events = audit_events(_delivered_state(), "t-1")
    delivery_event = next(event for event in events if event.kind == "delivery")
    assert "report_hash" in delivery_event.data
    assert delivery_event.data["cited"] == ["9f2c1a3b4d5e"]
    assert "£34,622.40" not in str(delivery_event.data)


def test_research_events_keep_the_url_without_the_page_text():
    state = _delivered_state(
        research=[
            ResearchResult(
                research_id="abc123abc123",
                kind="page",
                title="Income Tax rates",
                url="https://www.gov.uk/income-tax-rates",
                text="Page content that must not be audited.",
                fetched_at=datetime(2026, 10, 19, tzinfo=UTC),
            )
        ]
    )
    events = audit_events(state, "t-1")
    research_event = next(event for event in events if event.kind == "research")
    assert research_event.data["url"] == "https://www.gov.uk/income-tax-rates"
    assert "Page content" not in str(research_event.data)


def test_validation_events_keep_every_attempt_in_order():
    state = _delivered_state(
        validation_log=[
            Validation(status="failed", attempts=1, mismatches=["wrong"]),
            Validation(status="failed", attempts=2, mismatches=["still wrong"]),
            Validation(status="passed", attempts=3, mismatches=[]),
        ]
    )
    attempts = [
        (event.data["attempt"], event.data["status"])
        for event in audit_events(state, "t-1")
        if event.kind == "validation"
    ]
    assert attempts == [(1, "failed"), (2, "failed"), (3, "passed")]
