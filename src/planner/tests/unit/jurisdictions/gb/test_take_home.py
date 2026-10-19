import re

import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.take_home import (
    CALCULATOR_VERSION,
    TakeHomeInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def test_take_home_figures():
    result = calculate(
        TakeHomeInput(gross_annual=450_000_000, scottish_taxpayer=False), PACK
    )
    assert result.calculator == "gb.take_home"
    assert result.calculator_version == CALCULATOR_VERSION
    assert result.inputs == {"gross_annual": 450_000_000, "scottish_taxpayer": False}
    assert result.get("gross_annual") == 450_000_000
    assert result.get("income_tax") == 64_860_000
    assert result.get("national_insurance") == 25_944_000
    assert result.get("net_pay") == 359_196_000


def test_high_income_applies_the_allowance_taper():
    result = calculate(
        TakeHomeInput(gross_annual=1_200_000_000, scottish_taxpayer=False), PACK
    )
    assert result.get("personal_allowance") == 25_700_000
    assert result.get("taxable_income") == 1_174_300_000
    assert result.get("income_tax") == 396_750_000
    assert result.get("national_insurance") == 44_106_000
    assert result.get("net_pay") == 759_144_000


def test_result_id_is_stable_and_well_formed():
    calculator_input = TakeHomeInput(gross_annual=450_000_000, scottish_taxpayer=False)
    first = calculate(calculator_input, PACK)
    second = calculate(calculator_input, PACK)
    assert first.result_id == second.result_id
    assert re.fullmatch(r"[0-9a-f]{12}", first.result_id)


def test_result_id_differs_for_different_inputs():
    first = calculate(
        TakeHomeInput(gross_annual=450_000_000, scottish_taxpayer=False), PACK
    )
    second = calculate(
        TakeHomeInput(gross_annual=460_000_000, scottish_taxpayer=False), PACK
    )
    assert first.result_id != second.result_id


def test_every_figure_line_cites_rules():
    result = calculate(
        TakeHomeInput(gross_annual=450_000_000, scottish_taxpayer=False), PACK
    )
    for line in result.lines:
        if line.key in {"income_tax", "national_insurance", "net_pay"}:
            assert line.rule_ids, f"{line.key} must cite its rules"


def test_scottish_taxpayer_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(TakeHomeInput(gross_annual=450_000_000, scottish_taxpayer=True), PACK)
    assert "Scottish" in excinfo.value.reason


def test_values_come_from_the_pack_not_code():
    # Zero out the personal allowance: tax on 45,000 becomes 9,000 at 20%.
    changed = PACK.model_copy(deep=True)
    for rule in changed.rules:
        if rule.id == "gb.income_tax.personal_allowance":
            rule.value = "0.0000"
    result = calculate(
        TakeHomeInput(gross_annual=450_000_000, scottish_taxpayer=False), changed
    )
    assert result.get("income_tax") == 90_000_000
