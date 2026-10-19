import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"


class TakeHomeInput(BaseModel):
    gross_annual: StrictInt  # at fp.SCALE
    scottish_taxpayer: bool


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: TakeHomeInput) -> str:
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
            "gb.take_home",
            CALCULATOR_VERSION,
            {
                "gross_annual": calculator_input.gross_annual,
                "scottish_taxpayer": calculator_input.scottish_taxpayer,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calculate(calculator_input: TakeHomeInput, pack: RulePack) -> CalcResult:
    if calculator_input.scottish_taxpayer:
        raise Unsupported("Scottish income tax bands are not supported yet")

    values = _values(pack)
    gross = calculator_input.gross_annual
    standard_allowance = values["gb.income_tax.personal_allowance"]
    personal_allowance = helpers.personal_allowance_for(
        gross,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    taxable_income = max(gross - personal_allowance, 0)

    income_tax = helpers.income_tax(
        gross,
        personal_allowance=personal_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=values["gb.income_tax.basic_rate_limit"],
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        basic_rate=values["gb.income_tax.basic_rate"],
        higher_rate=values["gb.income_tax.higher_rate"],
        additional_rate=values["gb.income_tax.additional_rate"],
    )
    national_insurance_amount = helpers.national_insurance(
        gross,
        primary_threshold=values["gb.ni.primary_threshold"],
        upper_earnings_limit=values["gb.ni.upper_earnings_limit"],
        main_rate=values["gb.ni.main_rate"],
        additional_rate=values["gb.ni.additional_rate"],
    )
    net_pay = gross - income_tax - national_insurance_amount

    tax_rules = [
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
        "gb.income_tax.basic_rate",
    ]
    if gross > values["gb.income_tax.allowance_taper_threshold"]:
        tax_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    if gross > values["gb.income_tax.basic_rate_limit"]:
        tax_rules += ["gb.income_tax.higher_rate_limit", "gb.income_tax.higher_rate"]
    if gross > values["gb.income_tax.higher_rate_limit"]:
        tax_rules += ["gb.income_tax.additional_rate"]

    national_insurance_rules = [
        "gb.ni.primary_threshold",
        "gb.ni.upper_earnings_limit",
        "gb.ni.main_rate",
    ]
    if gross > values["gb.ni.upper_earnings_limit"]:
        national_insurance_rules += ["gb.ni.additional_rate"]

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.take_home",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "gross_annual": gross,
            "scottish_taxpayer": calculator_input.scottish_taxpayer,
        },
        lines=[
            CalcLine(key="gross_annual", amount=gross),
            CalcLine(
                key="personal_allowance",
                amount=personal_allowance,
                rule_ids=[
                    "gb.income_tax.personal_allowance",
                    "gb.income_tax.allowance_taper_threshold",
                    "gb.income_tax.allowance_taper_rate",
                ],
            ),
            CalcLine(key="taxable_income", amount=taxable_income),
            CalcLine(key="income_tax", amount=income_tax, rule_ids=tax_rules),
            CalcLine(
                key="national_insurance",
                amount=national_insurance_amount,
                rule_ids=national_insurance_rules,
            ),
            CalcLine(
                key="net_pay",
                amount=net_pay,
                rule_ids=[*tax_rules, *national_insurance_rules],
            ),
        ],
    )
