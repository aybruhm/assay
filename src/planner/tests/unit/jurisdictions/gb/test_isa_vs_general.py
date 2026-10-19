import re

import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.isa_vs_general import (
    CALCULATOR_VERSION,
    IsaVsGeneralInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def _input(**overrides: object) -> IsaVsGeneralInput:
    values: dict[str, object] = {
        "savings_amount": 100_000_000,
        "annual_growth_rate": 500,
        "investment_years": 10,
        "gross_annual": 200_000_000,
    }
    values.update(overrides)
    return IsaVsGeneralInput(**values)


def test_basic_rate_taxpayer_pays_capital_gains_tax_on_the_gain():
    result = calculate(_input(), PACK)
    assert result.calculator == "gb.isa_vs_general"
    assert result.calculator_version == CALCULATOR_VERSION
    assert result.get("savings_amount") == 100_000_000
    assert result.get("isa_allowance") == 200_000_000
    assert result.get("isa_value") == 162_889_462
    assert result.get("isa_tax") == 0
    assert result.get("isa_after_tax") == 162_889_462
    assert result.get("general_value") == 162_889_462
    assert result.get("general_gain") == 62_889_462
    assert result.get("annual_exempt_amount") == 30_000_000
    assert result.get("taxable_gain") == 32_889_462
    assert result.get("capital_gains_tax") == 5_920_103
    assert result.get("general_after_tax") == 156_969_359
    assert result.get("difference") == 5_920_103


def test_higher_rate_taxpayer_pays_the_higher_capital_gains_rate():
    result = calculate(_input(gross_annual=850_000_000), PACK)
    assert result.get("capital_gains_tax") == 7_893_471
    assert result.get("general_after_tax") == 154_995_991
    assert result.get("difference") == 7_893_471


def test_gain_below_the_annual_exempt_amount_has_no_capital_gains_tax():
    result = calculate(
        _input(annual_growth_rate=200, investment_years=1),
        PACK,
    )
    assert result.get("general_gain") == 2_000_000
    assert result.get("taxable_gain") == 0
    assert result.get("capital_gains_tax") == 0
    assert result.get("difference") == 0


def test_zero_growth_rate_is_allowed():
    result = calculate(_input(annual_growth_rate=0), PACK)
    assert result.get("isa_value") == 100_000_000
    assert result.get("general_gain") == 0
    assert result.get("capital_gains_tax") == 0
    assert result.get("difference") == 0


@pytest.mark.parametrize("years", [0, 101])
def test_investment_years_outside_the_supported_range_fail_closed(years):
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(investment_years=years), PACK)
    assert "years" in excinfo.value.reason


@pytest.mark.parametrize("rate", [-1, 10_001])
def test_growth_rate_outside_the_supported_range_fails_closed(rate):
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(annual_growth_rate=rate), PACK)
    assert "growth rate" in excinfo.value.reason


def test_savings_above_the_isa_allowance_fail_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(savings_amount=200_000_001), PACK)
    assert "ISA" in excinfo.value.reason


def test_zero_savings_fail_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(savings_amount=0), PACK)
    assert "savings" in excinfo.value.reason


def test_negative_income_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(gross_annual=-1), PACK)
    assert "income" in excinfo.value.reason


def test_capital_gains_and_isa_rules_are_cited():
    result = calculate(_input(), PACK)
    cgt = next(line for line in result.lines if line.key == "capital_gains_tax")
    assert "gb.capital_gains.annual_exempt_amount" in cgt.rule_ids
    assert "gb.capital_gains.basic_rate" in cgt.rule_ids
    assert "gb.capital_gains.higher_rate" in cgt.rule_ids
    isa_tax = next(line for line in result.lines if line.key == "isa_tax")
    assert isa_tax.rule_ids == ["gb.isa.tax_rate"]


def test_values_come_from_the_pack_not_code():
    changed = PACK.model_copy(deep=True)
    for rule in changed.rules:
        if rule.id == "gb.capital_gains.higher_rate":
            rule.value = "0.5000"
    result = calculate(_input(gross_annual=850_000_000), changed)
    assert result.get("capital_gains_tax") == 16_444_731


def test_result_id_is_stable_and_well_formed():
    first = calculate(_input(), PACK)
    second = calculate(_input(), PACK)
    assert first.result_id == second.result_id
    assert re.fullmatch(r"[0-9a-f]{12}", first.result_id)


def test_result_id_differs_for_different_inputs():
    first = calculate(_input(), PACK)
    second = calculate(_input(savings_amount=90_000_000), PACK)
    assert first.result_id != second.result_id
