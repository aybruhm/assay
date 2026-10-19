import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"


class PensionInput(BaseModel):
    gross_annual: StrictInt  # at fp.SCALE
    scottish_taxpayer: bool
    pension_rate: StrictInt  # at fp.SCALE


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: PensionInput) -> str:
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
            "gb.pension",
            CALCULATOR_VERSION,
            {
                "gross_annual": calculator_input.gross_annual,
                "scottish_taxpayer": calculator_input.scottish_taxpayer,
                "pension_rate": calculator_input.pension_rate,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calculate(calculator_input: PensionInput, pack: RulePack) -> CalcResult:
    if calculator_input.scottish_taxpayer:
        raise Unsupported("Scottish income tax bands are not supported yet")
    if not 0 < calculator_input.pension_rate <= fp.SCALE:
        raise Unsupported("pension rate must be between 0% and 100%")

    values = _values(pack)
    gross = calculator_input.gross_annual
    pension = helpers.pension_contribution(gross, calculator_input.pension_rate)
    taxable_pay = gross - pension
    standard_allowance = values["gb.income_tax.personal_allowance"]
    personal_allowance = helpers.personal_allowance_for(
        taxable_pay,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )

    income_tax = helpers.income_tax(
        taxable_pay,
        personal_allowance=personal_allowance,
        standard_personal_allowance=standard_allowance,
        basic_rate_limit=values["gb.income_tax.basic_rate_limit"],
        higher_rate_limit=values["gb.income_tax.higher_rate_limit"],
        basic_rate=values["gb.income_tax.basic_rate"],
        higher_rate=values["gb.income_tax.higher_rate"],
        additional_rate=values["gb.income_tax.additional_rate"],
    )
    national_insurance_amount = helpers.national_insurance(
        taxable_pay,
        primary_threshold=values["gb.ni.primary_threshold"],
        upper_earnings_limit=values["gb.ni.upper_earnings_limit"],
        main_rate=values["gb.ni.main_rate"],
        additional_rate=values["gb.ni.additional_rate"],
    )
    net_pay = gross - pension - income_tax - national_insurance_amount

    tax_rules = [
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
        "gb.income_tax.basic_rate",
    ]
    if taxable_pay > values["gb.income_tax.allowance_taper_threshold"]:
        tax_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    if taxable_pay > values["gb.income_tax.basic_rate_limit"]:
        tax_rules += ["gb.income_tax.higher_rate_limit", "gb.income_tax.higher_rate"]
    if taxable_pay > values["gb.income_tax.higher_rate_limit"]:
        tax_rules += ["gb.income_tax.additional_rate"]

    national_insurance_rules = [
        "gb.ni.primary_threshold",
        "gb.ni.upper_earnings_limit",
        "gb.ni.main_rate",
    ]
    if taxable_pay > values["gb.ni.upper_earnings_limit"]:
        national_insurance_rules += ["gb.ni.additional_rate"]

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.pension",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "gross_annual": gross,
            "scottish_taxpayer": calculator_input.scottish_taxpayer,
            "pension_rate": calculator_input.pension_rate,
        },
        lines=[
            CalcLine(key="gross_annual", amount=gross),
            CalcLine(key="pension_contribution", amount=pension),
            CalcLine(key="taxable_pay", amount=taxable_pay),
            CalcLine(
                key="personal_allowance",
                amount=personal_allowance,
                rule_ids=[
                    "gb.income_tax.personal_allowance",
                    "gb.income_tax.allowance_taper_threshold",
                    "gb.income_tax.allowance_taper_rate",
                ],
            ),
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
