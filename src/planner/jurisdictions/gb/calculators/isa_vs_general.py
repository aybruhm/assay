import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"
MAX_YEARS = 100


class IsaVsGeneralInput(BaseModel):
    savings_amount: StrictInt  # at fp.SCALE
    annual_growth_rate: StrictInt  # at fp.SCALE
    investment_years: StrictInt
    gross_annual: StrictInt  # at fp.SCALE


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: IsaVsGeneralInput) -> str:
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
            "gb.isa_vs_general",
            CALCULATOR_VERSION,
            {
                "savings_amount": calculator_input.savings_amount,
                "annual_growth_rate": calculator_input.annual_growth_rate,
                "investment_years": calculator_input.investment_years,
                "gross_annual": calculator_input.gross_annual,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _compound(amount: int, annual_growth_rate: int, years: int) -> int:
    value = amount
    growth_factor = fp.SCALE + annual_growth_rate
    for _year in range(years):
        value = fp.mul(value, growth_factor)
    return value


def calculate(calculator_input: IsaVsGeneralInput, pack: RulePack) -> CalcResult:
    if calculator_input.savings_amount <= 0:
        raise Unsupported("savings amount must be above zero")
    if not 0 <= calculator_input.annual_growth_rate <= fp.SCALE:
        raise Unsupported("annual growth rate must be between 0% and 100%")
    if not 1 <= calculator_input.investment_years <= MAX_YEARS:
        raise Unsupported(f"investment years must be between 1 and {MAX_YEARS}")
    if calculator_input.gross_annual < 0:
        raise Unsupported("gross annual income cannot be negative")

    values = _values(pack)
    isa_allowance = values["gb.isa.annual_allowance"]
    if calculator_input.savings_amount > isa_allowance:
        raise Unsupported("savings amount exceeds the ISA annual allowance")

    savings_amount = calculator_input.savings_amount
    annual_exempt_amount = values["gb.capital_gains.annual_exempt_amount"]
    standard_allowance = values["gb.income_tax.personal_allowance"]
    personal_allowance = helpers.personal_allowance_for(
        calculator_input.gross_annual,
        personal_allowance=standard_allowance,
        taper_threshold=values["gb.income_tax.allowance_taper_threshold"],
        taper_rate=values["gb.income_tax.allowance_taper_rate"],
    )
    final_value = _compound(
        savings_amount,
        calculator_input.annual_growth_rate,
        calculator_input.investment_years,
    )
    gain = max(final_value - savings_amount, 0)
    taxable_gain = max(gain - annual_exempt_amount, 0)

    isa_tax = helpers.isa_tax(final_value, rate=values["gb.isa.tax_rate"])
    isa_after_tax = final_value - isa_tax

    capital_gains_tax = helpers.capital_gains_tax(
        gain,
        other_income=calculator_input.gross_annual,
        personal_allowance=personal_allowance,
        standard_personal_allowance=standard_allowance,
        annual_exempt_amount=annual_exempt_amount,
        basic_rate_limit=values["gb.income_tax.basic_rate_limit"],
        basic_rate=values["gb.capital_gains.basic_rate"],
        higher_rate=values["gb.capital_gains.higher_rate"],
    )
    general_after_tax = final_value - capital_gains_tax
    difference = isa_after_tax - general_after_tax

    cgt_rules = [
        "gb.capital_gains.annual_exempt_amount",
        "gb.capital_gains.basic_rate",
        "gb.capital_gains.higher_rate",
        "gb.income_tax.personal_allowance",
        "gb.income_tax.basic_rate_limit",
    ]
    if (
        calculator_input.gross_annual
        > values["gb.income_tax.allowance_taper_threshold"]
    ):
        cgt_rules += [
            "gb.income_tax.allowance_taper_threshold",
            "gb.income_tax.allowance_taper_rate",
        ]
    isa_rules = ["gb.isa.tax_rate"]
    isa_allowance_rules = ["gb.isa.annual_allowance"]

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.isa_vs_general",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "savings_amount": savings_amount,
            "annual_growth_rate": calculator_input.annual_growth_rate,
            "investment_years": calculator_input.investment_years,
            "gross_annual": calculator_input.gross_annual,
        },
        lines=[
            CalcLine(key="savings_amount", amount=savings_amount),
            CalcLine(
                key="personal_allowance",
                amount=personal_allowance,
                rule_ids=cgt_rules,
            ),
            CalcLine(
                key="isa_allowance",
                amount=isa_allowance,
                rule_ids=isa_allowance_rules,
            ),
            CalcLine(key="isa_value", amount=final_value),
            CalcLine(key="isa_tax", amount=isa_tax, rule_ids=isa_rules),
            CalcLine(key="isa_after_tax", amount=isa_after_tax, rule_ids=isa_rules),
            CalcLine(key="general_value", amount=final_value),
            CalcLine(key="general_gain", amount=gain),
            CalcLine(
                key="annual_exempt_amount",
                amount=annual_exempt_amount,
                rule_ids=["gb.capital_gains.annual_exempt_amount"],
            ),
            CalcLine(key="taxable_gain", amount=taxable_gain, rule_ids=cgt_rules),
            CalcLine(
                key="capital_gains_tax",
                amount=capital_gains_tax,
                rule_ids=cgt_rules,
            ),
            CalcLine(
                key="general_after_tax",
                amount=general_after_tax,
                rule_ids=cgt_rules,
            ),
            CalcLine(
                key="difference",
                amount=difference,
                rule_ids=[*isa_allowance_rules, *isa_rules, *cgt_rules],
            ),
        ],
    )
