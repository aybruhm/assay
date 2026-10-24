from typing import Any

from planner.core import utils as fp
from planner.core.types import CalcResult, Unsupported
from planner.graph.state import PlanState, ToolRecord
from planner.research import research
from planner.rules.loader import NoRulePack, load_ref
from planner.tools.execute import execute_tool
from planner.tools.specs import ToolContext, ToolError


def _defaults(state: PlanState) -> dict[str, str | int | bool | None]:
    profile = state.profile
    values = {
        "gross_annual": profile.gross_annual,
        "scottish_taxpayer": profile.scottish_taxpayer,
        "pension_income": profile.pension_income,
        "rental_income": profile.rental_income,
        "other_income": profile.other_income,
        "student_loan_plan": profile.student_loan_plan,
        "pension_rate": profile.pension_rate,
        "company_profit": profile.company_profit,
        "director_salary": profile.director_salary,
        "distributable_reserves": profile.distributable_reserves,
        "savings_amount": profile.savings_amount,
        "annual_growth_rate": profile.annual_growth_rate,
        "investment_years": profile.investment_years,
    }
    defaults: dict[str, str | int | bool | None] = {}
    for key, value in values.items():
        if value is None or isinstance(value, (bool, str)) or key == "investment_years":
            defaults[key] = value
        else:
            defaults[key] = fp.format_amount(value)
    return defaults


async def execute_pending(state: PlanState) -> dict[str, Any]:
    if state.jurisdiction is None or state.rule_pack is None:
        return {"failure": "rule pack is not ready"}
    try:
        pack = load_ref(state.rule_pack)
    except NoRulePack as exc:
        return {"failure": str(exc)}

    context = ToolContext(
        jurisdiction=state.jurisdiction,
        pack=pack,
        defaults=_defaults(state),
        research=research(),
    )
    results = list(state.results)
    research_results = list(state.research)
    records = list(state.tool_records)

    for call in state.pending_calls:
        try:
            outcome = await execute_tool(call, context)
        except (ToolError, Unsupported) as exc:
            records.append(
                ToolRecord(name=call.name, arguments=call.arguments, error=exc.reason)
            )
            continue
        if isinstance(outcome, CalcResult):
            results.append(outcome)
            records.append(
                ToolRecord(
                    name=call.name,
                    arguments=call.arguments,
                    result_id=outcome.result_id,
                )
            )
            continue
        research_results.extend(outcome)
        records.append(
            ToolRecord(
                name=call.name,
                arguments=call.arguments,
                research_ids=[item.research_id for item in outcome],
            )
        )

    return {
        "results": results,
        "research": research_results,
        "tool_records": records,
        "pending_calls": [],
        "next_action": None,
    }
