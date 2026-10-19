import json
from datetime import date

from langchain_core.messages import HumanMessage

from planner.audit.events import audit_events
from planner.core.types import CalcLine, CalcResult
from planner.graph.state import (
    Citation,
    PlanState,
    Profile,
    Report,
    Validation,
)
from planner.rules.schema import RulePackRef

PROFILE_KEYS = {
    "gross_annual",
    "pension_income",
    "rental_income",
    "other_income",
    "student_loan_plan",
    "company_profit",
    "salary",
    "amount",
    "savings_amount",
    "annual_growth_rate",
    "investment_years",
    "distributable_reserves",
    "profile",
    "messages",
}


def _delivered_state() -> PlanState:
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
    return PlanState(
        messages=[HumanMessage(content="I earn 45,000 a year in England")],
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


def test_audit_contains_no_profile_data():
    state = _delivered_state()
    blob = json.dumps(
        [event.model_dump(mode="json") for event in audit_events(state, "t-1")]
    )
    for key in PROFILE_KEYS:
        assert f'"{key}"' not in blob, key
    assert str(state.profile.gross_annual) not in blob, "raw amount leaked into audit"
    assert "£34,622.40" not in blob, "report figures leaked into audit"
    assert "45,000" not in blob, "user message leaked into audit"
