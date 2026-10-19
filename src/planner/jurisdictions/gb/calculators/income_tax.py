import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"


class IncomeTaxInput(BaseModel):
    salary: StrictInt  # at fp.SCALE
    pension_income: StrictInt  # at fp.SCALE
    rental_income: StrictInt  # at fp.SCALE
    other_income: StrictInt  # at fp.SCALE
    scottish_taxpayer: bool


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: IncomeTaxInput) -> str:
    """
    Return a stable identifier for a calculator input.

    Args:
        calculator_input: The calculator input.

    Returns:
        The first 12 hex characters of the SHA-256 hash.
    """
    blob = json.dumps(
        [
            "gb.income_tax",
            CALCULATOR_VERSION,
            {
                "salary": calculator_input.salary,
                "pension_income": calculator_input.pension_income,
                "rental_income": calculator_input.rental_income,
                "other_income": calculator_input.other_income,
                "scottish_taxpayer": calculator_input.scottish_taxpayer,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calculate(calculator_input: IncomeTaxInput, pack: RulePack) -> CalcResult:
    if calculator_input.scottish_taxpayer:
        raise Unsupported("Scottish income tax bands are not supported yet")
    if (
        min(
            calculator_input.salary,
            calculator_input.pension_income,
            calculator_input.rental_income,
            calculator_input.other_income,
        )
        < 0
    ):
        raise Unsupported("income cannot be negative")

    values = _values(pack)
    standard_allowance = values["gb.income_tax.personal_allowance"]
    total_income = (
        calculator_input.salary
        + calculator_input.pension_income
        + calculator_input.rental_income
        + calculator_input.other_income
    )
    personal_allowance = helpers.personal_allowance_for(
        total_income,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    taxable_income = max(total_income - personal_allowance, 0)
    income_tax = helpers.income_tax(
        total_income,
        personal_allowance=personal_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=values["gb.income_tax.basic_rate_limit"],
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        basic_rate=values["gb.income_tax.basic_rate"],
        higher_rate=values["gb.income_tax.higher_rate"],
        additional_rate=values["gb.income_tax.additional_rate"],
    )
    national_insurance_amount = helpers.national_insurance(
        calculator_input.salary,
        primary_threshold=values["gb.ni.primary_threshold"],
        upper_earnings_limit=values["gb.ni.upper_earnings_limit"],
        main_rate=values["gb.ni.main_rate"],
        additional_rate=values["gb.ni.additional_rate"],
    )
    net_income = total_income - income_tax - national_insurance_amount

    tax_rules = [
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
        "gb.income_tax.basic_rate",
    ]
    if total_income > values["gb.income_tax.allowance_taper_threshold"]:
        tax_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    if total_income > values["gb.income_tax.basic_rate_limit"]:
        tax_rules += ["gb.income_tax.higher_rate_limit", "gb.income_tax.higher_rate"]
    if total_income > values["gb.income_tax.higher_rate_limit"]:
        tax_rules += ["gb.income_tax.additional_rate"]

    national_insurance_rules = [
        "gb.ni.primary_threshold",
        "gb.ni.upper_earnings_limit",
        "gb.ni.main_rate",
    ]
    if calculator_input.salary > values["gb.ni.upper_earnings_limit"]:
        national_insurance_rules += ["gb.ni.additional_rate"]

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.income_tax",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "salary": calculator_input.salary,
            "pension_income": calculator_input.pension_income,
            "rental_income": calculator_input.rental_income,
            "other_income": calculator_input.other_income,
            "scottish_taxpayer": calculator_input.scottish_taxpayer,
        },
        lines=[
            CalcLine(key="salary", amount=calculator_input.salary),
            CalcLine(key="pension_income", amount=calculator_input.pension_income),
            CalcLine(key="rental_income", amount=calculator_input.rental_income),
            CalcLine(key="other_income", amount=calculator_input.other_income),
            CalcLine(key="total_income", amount=total_income),
            CalcLine(
                key="personal_allowance",
                amount=personal_allowance,
                rule_ids=tax_rules,
            ),
            CalcLine(key="taxable_income", amount=taxable_income),
            CalcLine(key="income_tax", amount=income_tax, rule_ids=tax_rules),
            CalcLine(
                key="national_insurance",
                amount=national_insurance_amount,
                rule_ids=national_insurance_rules,
            ),
            CalcLine(
                key="net_income",
                amount=net_income,
                rule_ids=[*tax_rules, *national_insurance_rules],
            ),
        ],
    )
