import hashlib
import json

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"

# Structural, not values: the PIT table has six bands, the last open-ended.
# The limits and rates themselves come from the rule pack.
BAND_COUNT = 6


class TakeHomeInput(BaseModel):
    gross_annual: StrictInt  # at fp.SCALE
    annual_rent: StrictInt = 0  # at fp.SCALE; declared rent for the relief


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _rent_relief(rent: int, values: dict[str, int]) -> int:
    return min(
        values["ng.paye.rent_relief_limit"],
        fp.mul(rent, values["ng.paye.rent_relief_percent"]),
    )


def _banded_tax(taxable: int, values: dict[str, int]) -> int:
    tax = 0
    previous = 0
    for band in range(1, BAND_COUNT):
        limit = values[f"ng.paye.band_{band}_limit"]
        rate = values[f"ng.paye.rate_{band}"]
        if taxable > previous:
            width = min(taxable, limit) - previous
            tax += fp.mul(width, rate)
            previous = limit
    if taxable > previous:
        tax += fp.mul(taxable - previous, values[f"ng.paye.rate_{BAND_COUNT}"])
    return tax


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
            "ng.take_home",
            CALCULATOR_VERSION,
            {
                "gross_annual": calculator_input.gross_annual,
                "annual_rent": calculator_input.annual_rent,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calculate(calculator_input: TakeHomeInput, pack: RulePack) -> CalcResult:
    values = _values(pack)
    gross = calculator_input.gross_annual

    pension = fp.mul(gross, values["ng.pension.employee_rate"])
    rent_relief = _rent_relief(calculator_input.annual_rent, values)
    taxable = max(gross - pension - rent_relief, 0)
    if gross <= values["ng.paye.minimum_wage_annual"]:
        tax = 0
    else:
        tax = _banded_tax(taxable, values)

    # PwC's sample defines net income as gross less PAYE, pension and rent.
    net_pay = gross - tax - pension - calculator_input.annual_rent

    tax_rules = [
        "ng.paye.rent_relief_limit",
        "ng.paye.rent_relief_percent",
        *(f"ng.paye.band_{band}_limit" for band in range(1, BAND_COUNT)),
        *(f"ng.paye.rate_{band}" for band in range(1, BAND_COUNT + 1)),
    ]
    if gross <= values["ng.paye.minimum_wage_annual"]:
        tax_rules.append("ng.paye.minimum_wage_annual")

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="ng.take_home",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "gross_annual": gross,
            "annual_rent": calculator_input.annual_rent,
        },
        lines=[
            CalcLine(key="gross_annual", amount=gross),
            CalcLine(
                key="pension_contribution",
                amount=pension,
                rule_ids=["ng.pension.employee_rate"],
            ),
            CalcLine(
                key="rent_relief",
                amount=rent_relief,
                rule_ids=["ng.paye.rent_relief_limit", "ng.paye.rent_relief_percent"],
            ),
            CalcLine(key="taxable_income", amount=taxable, rule_ids=tax_rules),
            CalcLine(key="income_tax", amount=tax, rule_ids=tax_rules),
            CalcLine(
                key="net_pay",
                amount=net_pay,
                rule_ids=[*tax_rules, "ng.pension.employee_rate"],
            ),
        ],
    )
