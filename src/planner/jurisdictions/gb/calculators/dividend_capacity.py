import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"


class DividendCapacityInput(BaseModel):
    existing_paye_income: StrictInt  # at fp.SCALE
    company_profit: StrictInt  # at fp.SCALE
    director_salary: StrictInt  # at fp.SCALE
    distributable_reserves: StrictInt  # at fp.SCALE
    dividend_amount: StrictInt | None = None  # at fp.SCALE
    scottish_taxpayer: bool


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: DividendCapacityInput) -> str:
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
            "gb.dividend_capacity",
            CALCULATOR_VERSION,
            {
                "existing_paye_income": calculator_input.existing_paye_income,
                "company_profit": calculator_input.company_profit,
                "director_salary": calculator_input.director_salary,
                "distributable_reserves": calculator_input.distributable_reserves,
                "dividend_amount": calculator_input.dividend_amount,
                "scottish_taxpayer": calculator_input.scottish_taxpayer,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calculate(calculator_input: DividendCapacityInput, pack: RulePack) -> CalcResult:
    if calculator_input.scottish_taxpayer and calculator_input.director_salary > 0:
        raise Unsupported("Scottish income tax bands are not supported yet")
    if calculator_input.existing_paye_income < 0:
        raise Unsupported("existing PAYE income cannot be negative")
    if calculator_input.company_profit < 0:
        raise Unsupported("company profit cannot be negative")
    if calculator_input.director_salary < 0:
        raise Unsupported("director salary cannot be negative")
    if calculator_input.distributable_reserves < 0:
        raise Unsupported("distributable reserves cannot be negative")
    if calculator_input.director_salary > calculator_input.company_profit:
        raise Unsupported("director salary cannot exceed company profit")
    if (
        calculator_input.dividend_amount is not None
        and calculator_input.dividend_amount < 0
    ):
        raise Unsupported("dividend amount cannot be negative")

    values = _values(pack)
    existing_paye_income = calculator_input.existing_paye_income
    company_profit = calculator_input.company_profit
    director_salary = calculator_input.director_salary
    reserves = calculator_input.distributable_reserves
    standard_allowance = values["gb.income_tax.personal_allowance"]
    basic_rate_limit = values["gb.income_tax.basic_rate_limit"]
    dividend_allowance = values["gb.dividend.allowance"]

    employer_national_insurance = helpers.employer_national_insurance(
        director_salary,
        secondary_threshold=values["gb.ni.employer_secondary_threshold"],
        rate=values["gb.ni.employer_rate"],
    )
    profit_before_corporation_tax = max(
        company_profit - director_salary - employer_national_insurance, 0
    )
    corporation_tax = helpers.corporation_tax(
        profit_before_corporation_tax,
        small_profits_rate=values["gb.corporation_tax.small_profits_rate"],
        main_rate=values["gb.corporation_tax.main_rate"],
        lower_limit=values["gb.corporation_tax.lower_limit"],
        upper_limit=values["gb.corporation_tax.upper_limit"],
        marginal_relief_fraction=values["gb.corporation_tax.marginal_relief_fraction"],
    )
    post_tax_profit = max(profit_before_corporation_tax - corporation_tax, 0)
    available_dividend = reserves + post_tax_profit

    other_income = existing_paye_income + director_salary
    personal_allowance = helpers.personal_allowance_for(
        other_income,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    taxable_income = max(other_income - personal_allowance, 0)
    basic_band_end = max(basic_rate_limit - standard_allowance, 0)
    basic_room = max(basic_band_end - taxable_income, 0)
    basic_rate_dividend_capacity = min(
        available_dividend, max(basic_room, dividend_allowance)
    )

    dividend_taken = (
        available_dividend
        if calculator_input.dividend_amount is None
        else calculator_input.dividend_amount
    )
    if dividend_taken > available_dividend:
        raise Unsupported("dividend amount exceeds the available dividend")
    dividend_tax = helpers.dividend_tax(
        dividend_taken,
        other_income=other_income,
        personal_allowance=personal_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=basic_rate_limit,
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        allowance=dividend_allowance,
        basic_rate=values["gb.dividend.basic_rate"],
        higher_rate=values["gb.dividend.higher_rate"],
        additional_rate=values["gb.dividend.additional_rate"],
    )
    net_dividend = dividend_taken - dividend_tax
    remaining_reserves = available_dividend - dividend_taken

    existing_allowance = helpers.personal_allowance_for(
        existing_paye_income,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    salary_income_tax_total = helpers.income_tax(
        other_income,
        personal_allowance=personal_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=basic_rate_limit,
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        basic_rate=values["gb.income_tax.basic_rate"],
        higher_rate=values["gb.income_tax.higher_rate"],
        additional_rate=values["gb.income_tax.additional_rate"],
    )
    salary_income_tax_existing = helpers.income_tax(
        existing_paye_income,
        personal_allowance=existing_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=basic_rate_limit,
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        basic_rate=values["gb.income_tax.basic_rate"],
        higher_rate=values["gb.income_tax.higher_rate"],
        additional_rate=values["gb.income_tax.additional_rate"],
    )
    salary_income_tax = max(salary_income_tax_total - salary_income_tax_existing, 0)
    salary_national_insurance = helpers.national_insurance(
        director_salary,
        primary_threshold=values["gb.ni.primary_threshold"],
        upper_earnings_limit=values["gb.ni.upper_earnings_limit"],
        main_rate=values["gb.ni.main_rate"],
        additional_rate=values["gb.ni.additional_rate"],
    )
    salary_net = director_salary - salary_income_tax - salary_national_insurance

    income_tax_rules = [
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
        "gb.income_tax.basic_rate",
    ]
    if other_income > values["gb.income_tax.allowance_taper_threshold"]:
        income_tax_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    if other_income > basic_rate_limit:
        income_tax_rules += [
            "gb.income_tax.higher_rate_limit",
            "gb.income_tax.higher_rate",
        ]
    if other_income > values["gb.income_tax.higher_rate_limit"]:
        income_tax_rules += ["gb.income_tax.additional_rate"]

    national_insurance_rules = [
        "gb.ni.primary_threshold",
        "gb.ni.upper_earnings_limit",
        "gb.ni.main_rate",
    ]
    if director_salary > values["gb.ni.upper_earnings_limit"]:
        national_insurance_rules += ["gb.ni.additional_rate"]

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
    if other_income > values["gb.income_tax.allowance_taper_threshold"]:
        dividend_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    all_rules = sorted(
        {
            *income_tax_rules,
            *national_insurance_rules,
            *employer_ni_rules,
            *corporation_tax_rules,
            *dividend_rules,
        }
    )

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.dividend_capacity",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "existing_paye_income": existing_paye_income,
            "company_profit": company_profit,
            "director_salary": director_salary,
            "distributable_reserves": reserves,
            "dividend_amount": calculator_input.dividend_amount,
            "scottish_taxpayer": calculator_input.scottish_taxpayer,
        },
        lines=[
            CalcLine(key="existing_paye_income", amount=existing_paye_income),
            CalcLine(key="company_profit", amount=company_profit),
            CalcLine(key="director_salary", amount=director_salary),
            CalcLine(
                key="personal_allowance",
                amount=personal_allowance,
                rule_ids=income_tax_rules,
            ),
            CalcLine(key="taxable_income", amount=taxable_income),
            CalcLine(
                key="employer_national_insurance",
                amount=employer_national_insurance,
                rule_ids=employer_ni_rules,
            ),
            CalcLine(
                key="corporation_tax",
                amount=corporation_tax,
                rule_ids=corporation_tax_rules,
            ),
            CalcLine(key="post_tax_profit", amount=post_tax_profit),
            CalcLine(key="distributable_reserves", amount=reserves),
            CalcLine(key="available_dividend", amount=available_dividend),
            CalcLine(
                key="basic_rate_dividend_capacity",
                amount=basic_rate_dividend_capacity,
                rule_ids=dividend_rules,
            ),
            CalcLine(
                key="dividend_allowance",
                amount=dividend_allowance,
                rule_ids=["gb.dividend.allowance"],
            ),
            CalcLine(key="dividend_taken", amount=dividend_taken),
            CalcLine(
                key="dividend_tax",
                amount=dividend_tax,
                rule_ids=dividend_rules,
            ),
            CalcLine(key="net_dividend", amount=net_dividend, rule_ids=all_rules),
            CalcLine(key="remaining_reserves", amount=remaining_reserves),
            CalcLine(
                key="director_salary_income_tax",
                amount=salary_income_tax,
                rule_ids=income_tax_rules,
            ),
            CalcLine(
                key="director_salary_national_insurance",
                amount=salary_national_insurance,
                rule_ids=national_insurance_rules,
            ),
            CalcLine(key="director_salary_net", amount=salary_net, rule_ids=all_rules),
        ],
    )
