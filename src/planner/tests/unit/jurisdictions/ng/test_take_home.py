import re

from planner.jurisdictions.ng.calculators.take_home import (
    CALCULATOR_VERSION,
    TakeHomeInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("NG", "2026")


def _scale(ngn: int) -> int:
    return ngn * 10_000


def test_pwc_sample_calculation():
    """
    Check the PwC Nigeria sample PAYE calculation.

    The sample uses gross NGN 25,000,000 and rent NGN 2,000,000, reviewed on
    29 May 2026.

    Source:
        https://taxsummaries.pwc.com/nigeria/individual/sample-personal-income-tax-calculation
    """
    result = calculate(
        TakeHomeInput(gross_annual=_scale(25_000_000), annual_rent=_scale(2_000_000)),
        PACK,
    )
    assert result.calculator == "ng.take_home"
    assert result.calculator_version == CALCULATOR_VERSION
    assert result.get("pension_contribution") == _scale(2_000_000)
    assert result.get("rent_relief") == _scale(400_000)
    assert result.get("taxable_income") == _scale(22_600_000)
    assert result.get("income_tax") == _scale(4_176_000)
    # PwC's "net income" line is taxable less tax (18,424,000); our net_pay
    # additionally subtracts the actual pension and rent cash outflows.
    assert result.get("taxable_income") - result.get("income_tax") == _scale(18_424_000)
    assert result.get("net_pay") == _scale(16_824_000)


def test_no_rent_declared_means_no_rent_relief():
    result = calculate(TakeHomeInput(gross_annual=_scale(3_000_000)), PACK)
    assert result.get("rent_relief") == 0
    # taxable = 3,000,000 - 240,000 pension = 2,760,000
    assert result.get("taxable_income") == _scale(2_760_000)
    # tax = 800,000*0% + 1,960,000*15% = 294,000
    assert result.get("income_tax") == _scale(294_000)
    assert result.get("net_pay") == _scale(2_466_000)


def test_minimum_wage_earners_pay_no_tax():
    result = calculate(
        TakeHomeInput(gross_annual=_scale(70_000 * 12)),
        PACK,  # NGN 840,000/year
    )
    assert result.get("income_tax") == 0
    assert result.get("net_pay") == _scale(840_000) - result.get("pension_contribution")


def test_top_band():
    result = calculate(TakeHomeInput(gross_annual=_scale(100_000_000)), PACK)
    # taxable = 100,000,000 - 8,000,000 = 92,000,000
    # 0 + 330,000 + 1,620,000 + 2,730,000 + 5,750,000 + 42,000,000*25%
    assert result.get("income_tax") == _scale(20_930_000)


def test_result_id_is_stable_and_well_formed():
    calculator_input = TakeHomeInput(
        gross_annual=_scale(25_000_000), annual_rent=_scale(2_000_000)
    )
    first = calculate(calculator_input, PACK)
    second = calculate(calculator_input, PACK)
    assert first.result_id == second.result_id
    assert re.fullmatch(r"[0-9a-f]{12}", first.result_id)


def test_every_figure_line_cites_rules():
    result = calculate(TakeHomeInput(gross_annual=_scale(3_000_000)), PACK)
    for line in result.lines:
        if line.key != "gross_annual":
            assert line.rule_ids, f"{line.key} must cite its rules"


def test_values_come_from_the_pack_not_code():
    changed = PACK.model_copy(deep=True)
    for rule in changed.rules:
        if rule.id == "ng.paye.rate_2":
            rule.value = "0.0000"
    result = calculate(TakeHomeInput(gross_annual=_scale(3_000_000)), changed)
    # Band 2 at 0% instead of 15%: tax drops from 294,000 to 0.
    assert result.get("income_tax") == 0
