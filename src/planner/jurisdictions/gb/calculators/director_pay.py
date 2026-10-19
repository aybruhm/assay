import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"


class DirectorPayInput(BaseModel):
    company_profit: StrictInt  # at fp.SCALE
    director_salary: StrictInt  # at fp.SCALE
    scottish_taxpayer: bool


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: DirectorPayInput) -> str:
    """
    Return a stable identifier for a calculator input.

    The same inputs always produce the same id, so resume and replay never
    change a figure.

    Args:
        calculator_input: The calculator input.

    Returns:
        The first 12 hex characters of the SHA-256 hash.
    """
    blob = json.dumps(
        [
            "gb.director_pay",
            CALCULATOR_VERSION,
            {
                "company_profit": calculator_input.company_profit,
                "director_salary": calculator_input.director_salary,
                "scottish_taxpayer": calculator_input.scottish_taxpayer,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _income_tax(gross: int, allowance: int, values: dict[str, int]) -> int:
    return helpers.income_tax(
        gross,
        personal_allowance=allowance,
        standard_personal_allowance=values["gb.income_tax.personal_allowance"],
        basic_rate_limit=values["gb.income_tax.basic_rate_limit"],
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        basic_rate=values["gb.income_tax.basic_rate"],
        higher_rate=values["gb.income_tax.higher_rate"],
        additional_rate=values["gb.income_tax.additional_rate"],
    )


def _employee_national_insurance(gross: int, values: dict[str, int]) -> int:
    return helpers.national_insurance(
        gross,
        primary_threshold=values["gb.ni.primary_threshold"],
        upper_earnings_limit=values["gb.ni.upper_earnings_limit"],
        main_rate=values["gb.ni.main_rate"],
        additional_rate=values["gb.ni.additional_rate"],
    )


def _employer_national_insurance(salary: int, values: dict[str, int]) -> int:
    return helpers.employer_national_insurance(
        salary,
        secondary_threshold=values["gb.ni.employer_secondary_threshold"],
        rate=values["gb.ni.employer_rate"],
    )


def _corporation_tax(profit: int, values: dict[str, int]) -> int:
    return helpers.corporation_tax(
        profit,
        small_profits_rate=values["gb.corporation_tax.small_profits_rate"],
        main_rate=values["gb.corporation_tax.main_rate"],
        lower_limit=values["gb.corporation_tax.lower_limit"],
        upper_limit=values["gb.corporation_tax.upper_limit"],
        marginal_relief_fraction=values["gb.corporation_tax.marginal_relief_fraction"],
    )


def _paye_gross_salary(company_cost: int, values: dict[str, int]) -> int:
    threshold = values["gb.ni.employer_secondary_threshold"]
    rate = values["gb.ni.employer_rate"]
    if company_cost <= threshold:
        return company_cost
    numerator = company_cost * fp.SCALE + threshold * rate
    denominator = fp.SCALE + rate
    return fp.divide(numerator, denominator)


def calculate(calculator_input: DirectorPayInput, pack: RulePack) -> CalcResult:
    if calculator_input.scottish_taxpayer:
        raise Unsupported("Scottish income tax bands are not supported yet")
    if calculator_input.company_profit <= 0:
        raise Unsupported("company profit must be above zero")
    if not 0 <= calculator_input.director_salary <= calculator_input.company_profit:
        raise Unsupported("director salary must be between zero and company profit")

    values = _values(pack)
    profit = calculator_input.company_profit
    salary = calculator_input.director_salary

    employer_ni = _employer_national_insurance(salary, values)
    profit_before_corporation_tax = max(profit - salary - employer_ni, 0)
    corporation_tax = _corporation_tax(profit_before_corporation_tax, values)
    dividends = max(profit_before_corporation_tax - corporation_tax, 0)

    standard_allowance = values["gb.income_tax.personal_allowance"]
    salary_allowance = helpers.personal_allowance_for(
        salary,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    employee_ni = _employee_national_insurance(salary, values)
    income_tax = _income_tax(salary, salary_allowance, values)
    dividend_tax = helpers.dividend_tax(
        dividends,
        other_income=salary,
        personal_allowance=salary_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=values["gb.income_tax.basic_rate_limit"],
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        allowance=values["gb.dividend.allowance"],
        basic_rate=values["gb.dividend.basic_rate"],
        higher_rate=values["gb.dividend.higher_rate"],
        additional_rate=values["gb.dividend.additional_rate"],
    )
    net_pay = salary - employee_ni - income_tax + dividends - dividend_tax

    paye_salary = _paye_gross_salary(profit, values)
    paye_allowance = helpers.personal_allowance_for(
        paye_salary,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    paye_employer_ni = _employer_national_insurance(paye_salary, values)
    paye_employee_ni = _employee_national_insurance(paye_salary, values)
    paye_income_tax = _income_tax(paye_salary, paye_allowance, values)
    paye_net_pay = paye_salary - paye_employee_ni - paye_income_tax
    difference = net_pay - paye_net_pay

    income_tax_rules = [
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
        "gb.income_tax.basic_rate",
    ]
    if salary > values["gb.income_tax.allowance_taper_threshold"]:
        income_tax_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    if salary > values["gb.income_tax.basic_rate_limit"]:
        income_tax_rules += [
            "gb.income_tax.higher_rate_limit",
            "gb.income_tax.higher_rate",
        ]
    if salary > values["gb.income_tax.higher_rate_limit"]:
        income_tax_rules += ["gb.income_tax.additional_rate"]

    employee_ni_rules = [
        "gb.ni.primary_threshold",
        "gb.ni.upper_earnings_limit",
        "gb.ni.main_rate",
    ]
    if salary > values["gb.ni.upper_earnings_limit"]:
        employee_ni_rules += ["gb.ni.additional_rate"]

    employer_ni_rules = [
        "gb.ni.employer_secondary_threshold",
        "gb.ni.employer_rate",
    ]
    corporation_tax_rules = [
        "gb.corporation_tax.small_profits_rate",
        "gb.corporation_tax.main_rate",
        "gb.corporation_tax.lower_limit",
        "gb.corporation_tax.upper_limit",
        "gb.corporation_tax.marginal_relief_fraction",
    ]
    dividend_rules = [
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
        "gb.income_tax.higher_rate_limit",
        "gb.dividend.allowance",
        "gb.dividend.basic_rate",
        "gb.dividend.higher_rate",
        "gb.dividend.additional_rate",
    ]
    all_rules = sorted(
        {
            *income_tax_rules,
            *employee_ni_rules,
            *employer_ni_rules,
            *corporation_tax_rules,
            *dividend_rules,
        }
    )

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.director_pay",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "company_profit": profit,
            "director_salary": salary,
            "scottish_taxpayer": calculator_input.scottish_taxpayer,
        },
        lines=[
            CalcLine(key="company_profit", amount=profit),
            CalcLine(key="director_salary", amount=salary),
            CalcLine(
                key="personal_allowance",
                amount=salary_allowance,
                rule_ids=[
                    "gb.income_tax.personal_allowance",
                    "gb.income_tax.allowance_taper_threshold",
                    "gb.income_tax.allowance_taper_rate",
                ],
            ),
            CalcLine(
                key="employer_national_insurance",
                amount=employer_ni,
                rule_ids=employer_ni_rules,
            ),
            CalcLine(
                key="corporation_tax",
                amount=corporation_tax,
                rule_ids=corporation_tax_rules,
            ),
            CalcLine(key="dividends", amount=dividends),
            CalcLine(
                key="employee_national_insurance",
                amount=employee_ni,
                rule_ids=employee_ni_rules,
            ),
            CalcLine(key="income_tax", amount=income_tax, rule_ids=income_tax_rules),
            CalcLine(
                key="dividend_tax",
                amount=dividend_tax,
                rule_ids=dividend_rules,
            ),
            CalcLine(key="net_pay", amount=net_pay, rule_ids=all_rules),
            CalcLine(key="paye_gross_salary", amount=paye_salary),
            CalcLine(
                key="paye_employer_national_insurance",
                amount=paye_employer_ni,
                rule_ids=employer_ni_rules,
            ),
            CalcLine(
                key="paye_employee_national_insurance",
                amount=paye_employee_ni,
                rule_ids=employee_ni_rules,
            ),
            CalcLine(
                key="paye_income_tax",
                amount=paye_income_tax,
                rule_ids=income_tax_rules,
            ),
            CalcLine(key="paye_net_pay", amount=paye_net_pay, rule_ids=all_rules),
            CalcLine(key="difference", amount=difference, rule_ids=all_rules),
        ],
    )
