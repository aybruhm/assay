import hashlib
import json
from datetime import UTC, datetime
from typing import Literal, cast

from pydantic import BaseModel, ValidationError

from planner.agent.models import ToolCall
from planner.agent.parsing import parse_amount, parse_rate, parse_years
from planner.core.types import CalcLine, CalcResult
from planner.jurisdictions.gb.calculators.director_pay import DirectorPayInput
from planner.jurisdictions.gb.calculators.dividend_capacity import (
    DividendCapacityInput,
)
from planner.jurisdictions.gb.calculators.income_tax import IncomeTaxInput
from planner.jurisdictions.gb.calculators.isa_vs_general import IsaVsGeneralInput
from planner.jurisdictions.gb.calculators.pension import PensionInput
from planner.jurisdictions.gb.calculators.student_loan import (
    StudentLoanInput,
    StudentLoanPlan,
)
from planner.jurisdictions.gb.calculators.take_home import (
    TakeHomeInput as GbTakeHomeInput,
)
from planner.jurisdictions.ng.calculators.take_home import (
    TakeHomeInput as NgTakeHomeInput,
)
from planner.jurisdictions.registry import REGISTRY
from planner.research.allowlist import is_allowed_url
from planner.research.models import ResearchResult
from planner.research.ports import ResearchError
from planner.tools.specs import (
    DirectorPayArgs,
    DividendCapacityArgs,
    FetchSourceArgs,
    IncomeTaxArgs,
    IsaVsGeneralArgs,
    LookupRuleArgs,
    PensionArgs,
    SearchSourcesArgs,
    StudentLoanArgs,
    TakeHomeArgs,
    ToolContext,
    ToolError,
    ToolSpec,
)

ToolOutcome = CalcResult | list[ResearchResult]


def result_from(
    template: str,
    calculator_input: BaseModel,
    context: ToolContext,
) -> CalcResult:
    _, calculator = REGISTRY[context.jurisdiction].calculator(template)
    return calculator(calculator_input, context.pack)


def _raw(
    argument: str | int | bool | None,
    field: str,
    context: ToolContext,
) -> str | int | bool | None:
    if argument is not None:
        return argument
    return context.defaults.get(field)


def _amount(argument: str | None, field: str, context: ToolContext) -> int:
    value = _raw(argument, field, context)
    if value is None:
        raise ToolError(f"{field} is required")
    if isinstance(value, bool):
        raise ToolError(f"{field} must be an amount")
    try:
        return parse_amount(str(value))
    except ValueError as exc:
        raise ToolError(f"{field} is not an amount: {value!r}") from exc


def _optional_amount(
    argument: str | None,
    field: str,
    context: ToolContext,
    default: int | None,
) -> int | None:
    value = _raw(argument, field, context)
    if value is None:
        return default
    if isinstance(value, bool):
        raise ToolError(f"{field} must be an amount")
    try:
        return parse_amount(str(value))
    except ValueError as exc:
        raise ToolError(f"{field} is not an amount: {value!r}") from exc


def _rate(argument: str | None, field: str, context: ToolContext) -> int:
    value = _raw(argument, field, context)
    if value is None:
        raise ToolError(f"{field} is required")
    if isinstance(value, bool):
        raise ToolError(f"{field} must be a rate")
    try:
        return parse_rate(str(value))
    except ValueError as exc:
        raise ToolError(f"{field} is not a rate: {value!r}") from exc


def _years(argument: int | str | None, field: str, context: ToolContext) -> int:
    value = _raw(argument, field, context)
    if value is None:
        raise ToolError(f"{field} is required")
    if isinstance(value, bool):
        raise ToolError(f"{field} must be a number of years")
    try:
        return parse_years(value)
    except ValueError as exc:
        raise ToolError(f"{field} is not a number of years: {value!r}") from exc


def _flag(argument: bool | None, field: str, context: ToolContext) -> bool:
    if argument is not None:
        return argument
    value = context.defaults.get(field)
    if isinstance(value, bool):
        return value
    raise ToolError(f"{field} is required")


def _take_home(arguments: TakeHomeArgs, context: ToolContext) -> CalcResult:
    gross = _amount(arguments.gross_annual, "gross_annual", context)
    if context.jurisdiction == "NG":
        ng_input = NgTakeHomeInput(gross_annual=gross)
        return result_from("ng.take_home", ng_input, context)
    if context.jurisdiction == "GB":
        scottish = _flag(arguments.scottish_taxpayer, "scottish_taxpayer", context)
        gb_input = GbTakeHomeInput(gross_annual=gross, scottish_taxpayer=scottish)
        return result_from("gb.take_home", gb_input, context)
    raise ToolError(f"take_home is not supported for {context.jurisdiction}")


def _pension(arguments: PensionArgs, context: ToolContext) -> CalcResult:
    if context.jurisdiction != "GB":
        raise ToolError("pension is only supported for GB")
    gross = _amount(arguments.gross_annual, "gross_annual", context)
    rate = _rate(arguments.pension_rate, "pension_rate", context)
    scottish = _flag(arguments.scottish_taxpayer, "scottish_taxpayer", context)
    return result_from(
        "gb.pension",
        PensionInput(
            gross_annual=gross,
            scottish_taxpayer=scottish,
            pension_rate=rate,
        ),
        context,
    )


def _director_pay(arguments: DirectorPayArgs, context: ToolContext) -> CalcResult:
    if context.jurisdiction != "GB":
        raise ToolError("director_pay is only supported for GB")
    profit = _amount(arguments.company_profit, "company_profit", context)
    salary = _amount(arguments.director_salary, "director_salary", context)
    scottish = _flag(arguments.scottish_taxpayer, "scottish_taxpayer", context)
    return result_from(
        "gb.director_pay",
        DirectorPayInput(
            company_profit=profit,
            director_salary=salary,
            scottish_taxpayer=scottish,
        ),
        context,
    )


def _dividend_capacity(
    arguments: DividendCapacityArgs, context: ToolContext
) -> CalcResult:
    if context.jurisdiction != "GB":
        raise ToolError("dividend_capacity is only supported for GB")
    paye_income = _amount(arguments.existing_paye_income, "gross_annual", context)
    profit = _amount(arguments.company_profit, "company_profit", context)
    salary = _optional_amount(arguments.director_salary, "director_salary", context, 0)
    reserves = _amount(
        arguments.distributable_reserves, "distributable_reserves", context
    )
    dividend_amount = _optional_amount(
        arguments.dividend_amount, "dividend_amount", context, None
    )
    scottish = arguments.scottish_taxpayer
    if scottish is None:
        default = context.defaults.get("scottish_taxpayer")
        scottish = default if isinstance(default, bool) else None
    if scottish is None and salary and salary > 0:
        raise ToolError("scottish_taxpayer is required when director salary is paid")
    assert salary is not None
    return result_from(
        "gb.dividend_capacity",
        DividendCapacityInput(
            existing_paye_income=paye_income,
            company_profit=profit,
            director_salary=salary,
            distributable_reserves=reserves,
            dividend_amount=dividend_amount,
            scottish_taxpayer=bool(scottish),
        ),
        context,
    )


def _income_tax(arguments: IncomeTaxArgs, context: ToolContext) -> CalcResult:
    if context.jurisdiction != "GB":
        raise ToolError("income_tax is only supported for GB")
    salary = _optional_amount(arguments.salary, "gross_annual", context, 0)
    pension_income = _optional_amount(
        arguments.pension_income, "pension_income", context, 0
    )
    rental_income = _optional_amount(
        arguments.rental_income, "rental_income", context, 0
    )
    other_income = _optional_amount(arguments.other_income, "other_income", context, 0)
    scottish = _flag(arguments.scottish_taxpayer, "scottish_taxpayer", context)
    assert salary is not None
    assert pension_income is not None
    assert rental_income is not None
    assert other_income is not None
    return result_from(
        "gb.income_tax",
        IncomeTaxInput(
            salary=salary,
            pension_income=pension_income,
            rental_income=rental_income,
            other_income=other_income,
            scottish_taxpayer=scottish,
        ),
        context,
    )


def _student_loan(arguments: StudentLoanArgs, context: ToolContext) -> CalcResult:
    if context.jurisdiction != "GB":
        raise ToolError("student_loan is only supported for GB")
    gross = _amount(arguments.gross_annual, "gross_annual", context)
    raw_plan = arguments.plan or context.defaults.get("student_loan_plan")
    if not isinstance(raw_plan, str) or not raw_plan.strip():
        raise ToolError("student loan plan is required")
    plan_text = raw_plan.strip().lower().replace(" ", "")
    plans: dict[str, StudentLoanPlan] = {
        "plan1": "plan1",
        "plan2": "plan2",
        "plan4": "plan4",
        "plan5": "plan5",
        "postgraduate": "postgraduate",
        "postgrad": "postgraduate",
    }
    plan = plans.get(plan_text)
    if plan is None:
        raise ToolError(f"unknown student loan plan: {raw_plan!r}")
    return result_from(
        "gb.student_loan",
        StudentLoanInput(gross_annual=gross, plan=plan),
        context,
    )


def _lookup_rule(arguments: LookupRuleArgs, context: ToolContext) -> CalcResult:
    rule = next(
        (rule for rule in context.pack.rules if rule.id == arguments.rule_id), None
    )
    if rule is None:
        raise ToolError(f"unknown rule: {arguments.rule_id}")
    if rule.kind not in {"amount", "rate", "flag"}:
        raise ToolError(f"rule kind {rule.kind} is not supported")
    display_kinds: dict[str, Literal["money", "rate", "text"]] = {
        "amount": "money",
        "rate": "rate",
        "flag": "text",
    }
    display_as = display_kinds[rule.kind]
    try:
        amount = parse_amount(rule.value)
    except ValueError as exc:
        raise ToolError(f"rule value is not a number: {rule.value!r}") from exc
    blob = json.dumps(
        [
            context.jurisdiction,
            context.pack.tax_year,
            context.pack.version,
            rule.id,
        ],
        sort_keys=True,
    )
    result_id = hashlib.sha256(blob.encode()).hexdigest()[:12]
    return CalcResult(
        result_id=result_id,
        calculator=f"{context.jurisdiction.lower()}.lookup_rule",
        calculator_version="1",
        inputs={"rule_id": rule.id},
        lines=[
            CalcLine(
                key="value",
                amount=amount,
                rule_ids=[rule.id],
                display_as=display_as,
                source=rule.source,
            )
        ],
    )


def _research_id(kind: str, url: str, query: str | None) -> str:
    blob = json.dumps([kind, url, query], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _search_trusted_sources(
    arguments: SearchSourcesArgs, context: ToolContext
) -> list[ResearchResult]:
    if context.research is None:
        raise ToolError("research is not configured")
    max_results = arguments.max_results or 5
    if not 1 <= max_results <= 10:
        raise ToolError("max_results must be between 1 and 10")
    try:
        hits = context.research.search(arguments.query, max_results)
    except ResearchError as exc:
        raise ToolError(exc.reason) from exc
    fetched_at = datetime.now(UTC)
    return [
        ResearchResult(
            research_id=_research_id("search", hit.url, arguments.query),
            kind="search",
            title=hit.title,
            url=hit.url,
            snippet=hit.snippet,
            query=arguments.query,
            fetched_at=fetched_at,
        )
        for hit in hits
        if is_allowed_url(hit.url)
    ]


def _fetch_source(
    arguments: FetchSourceArgs, context: ToolContext
) -> list[ResearchResult]:
    if context.research is None:
        raise ToolError("research is not configured")
    if not is_allowed_url(arguments.url):
        raise ToolError(f"not a trusted source: {arguments.url}")
    try:
        page = context.research.fetch(arguments.url)
    except ResearchError as exc:
        raise ToolError(exc.reason) from exc
    return [
        ResearchResult(
            research_id=_research_id("page", page.url, None),
            kind="page",
            title=page.title,
            url=page.url,
            text=page.text,
            fetched_at=page.fetched_at,
        )
    ]


def _isa_vs_general(arguments: IsaVsGeneralArgs, context: ToolContext) -> CalcResult:
    if context.jurisdiction != "GB":
        raise ToolError("isa_vs_general is only supported for GB")
    amount = _amount(arguments.savings_amount, "savings_amount", context)
    growth = _rate(arguments.annual_growth_rate, "annual_growth_rate", context)
    years = _years(arguments.investment_years, "investment_years", context)
    income = _amount(arguments.gross_annual, "gross_annual", context)
    return result_from(
        "gb.isa_vs_general",
        IsaVsGeneralInput(
            savings_amount=amount,
            annual_growth_rate=growth,
            investment_years=years,
            gross_annual=income,
        ),
        context,
    )


TOOLS: dict[str, ToolSpec] = {
    "take_home": ToolSpec(
        name="take_home",
        args_model=TakeHomeArgs,
        handler=_take_home,
    ),
    "pension": ToolSpec(
        name="pension",
        args_model=PensionArgs,
        handler=_pension,
    ),
    "director_pay": ToolSpec(
        name="director_pay",
        args_model=DirectorPayArgs,
        handler=_director_pay,
    ),
    "dividend_capacity": ToolSpec(
        name="dividend_capacity",
        args_model=DividendCapacityArgs,
        handler=_dividend_capacity,
    ),
    "isa_vs_general": ToolSpec(
        name="isa_vs_general",
        args_model=IsaVsGeneralArgs,
        handler=_isa_vs_general,
    ),
    "income_tax": ToolSpec(
        name="income_tax",
        args_model=IncomeTaxArgs,
        handler=_income_tax,
    ),
    "student_loan": ToolSpec(
        name="student_loan",
        args_model=StudentLoanArgs,
        handler=_student_loan,
    ),
    "lookup_rule": ToolSpec(
        name="lookup_rule",
        args_model=LookupRuleArgs,
        handler=_lookup_rule,
    ),
    "search_trusted_sources": ToolSpec(
        name="search_trusted_sources",
        args_model=SearchSourcesArgs,
        handler=_search_trusted_sources,
    ),
    "fetch_source": ToolSpec(
        name="fetch_source",
        args_model=FetchSourceArgs,
        handler=_fetch_source,
    ),
}


def execute_tool(call: ToolCall, context: ToolContext) -> ToolOutcome:
    """
    Validate a tool call and run its calculator.

    Args:
        call: The tool name and arguments chosen by the model.
        context: The run's jurisdiction, rule pack and profile defaults.

    Returns:
        The calculator result.

    Raises:
        ToolError: If the tool is unknown, its arguments are invalid, or the
            calculator cannot answer.
    """
    spec = TOOLS.get(call.name)
    if spec is None:
        raise ToolError(f"unknown tool: {call.name}")
    try:
        arguments = spec.args_model.model_validate(call.arguments)
    except ValidationError as exc:
        raise ToolError(f"invalid arguments for {call.name}: {exc}") from exc
    return cast(ToolOutcome, spec.handler(arguments, context))
