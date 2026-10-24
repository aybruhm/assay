import re

import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.dividend_capacity import (
    CALCULATOR_VERSION,
    DividendCapacityInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def _input(**overrides: object) -> DividendCapacityInput:
    values: dict[str, object] = {
        "existing_paye_income": 850_000_000,
        "company_profit": 1_000_000_000,
        "director_salary": 0,
        "distributable_reserves": 0,
        "scottish_taxpayer": False,
    }
    values.update(overrides)
    return DividendCapacityInput(**values)


def test_high_paye_income_leaves_only_the_dividend_allowance_before_the_higher_rate():
    result = calculate(_input(), PACK)
    assert result.calculator == "gb.dividend_capacity"
    assert result.calculator_version == CALCULATOR_VERSION
    assert result.get("corporation_tax") == 227_500_000
    assert result.get("post_tax_profit") == 772_500_000
    assert result.get("available_dividend") == 772_500_000
    assert result.get("dividend_before_higher_rate") == 5_000_000
    assert result.get("dividend_taken") == 772_500_000
    assert result.get("dividend_tax") == 292_266_050
    assert result.get("net_dividend") == 429_953_950
    assert result.get("remaining_reserves") == 0


def test_high_paye_income_uses_the_tapered_allowance():
    result = calculate(
        _input(existing_paye_income=1_200_000_000, dividend_amount=0), PACK
    )
    assert result.get("personal_allowance") == 25_700_000
    assert result.get("taxable_income") == 1_174_300_000
    assert result.get("dividend_tax") == 0
    assert result.get("dividend_within_taper_threshold") == 0


def test_dividend_above_the_taper_threshold_removes_the_allowance():
    result = calculate(_input(), PACK)
    assert result.get("total_income") == 1_622_500_000
    assert result.get("personal_allowance") == 0
    assert result.get("allowance_lost_to_dividend") == 125_700_000
    assert result.get("taper_income_tax") == 50_280_000
    assert result.get("total_tax_on_dividend") == 342_546_050


def test_dividend_tapers_an_allowance_already_reduced_by_paye():
    result = calculate(_input(existing_paye_income=1_200_000_000), PACK)
    assert result.get("personal_allowance") == 0
    assert result.get("allowance_lost_to_dividend") == 25_700_000
    assert result.get("dividend_tax") == 302_011_250
    assert result.get("taper_income_tax") == 11_565_000


def test_dividend_within_taper_threshold_keeps_the_allowance_whole():
    room = calculate(_input(), PACK).get("dividend_within_taper_threshold")
    assert room == 150_000_000
    result = calculate(_input(dividend_amount=room), PACK)
    assert result.get("taper_threshold") == 1_000_000_000
    assert result.get("total_income") == 1_000_000_000
    assert result.get("personal_allowance") == 125_700_000
    assert result.get("allowance_lost_to_dividend") == 0
    assert result.get("taper_income_tax") == 0


def test_dividend_within_taper_threshold_is_capped_by_the_available_dividend():
    result = calculate(_input(company_profit=100_000_000), PACK)
    assert result.get("available_dividend") == 81_000_000
    assert result.get("dividend_within_taper_threshold") == 81_000_000


def test_low_paye_income_leaves_basic_band_for_the_dividend():
    result = calculate(_input(existing_paye_income=200_000_000), PACK)
    assert result.get("dividend_before_higher_rate") == 302_700_000
    assert result.get("dividend_tax") == 199_956_250
    assert result.get("net_dividend") == 572_543_750


def test_unused_personal_allowance_counts_towards_the_dividend_capacity():
    result = calculate(_input(existing_paye_income=0), PACK)
    assert result.get("dividend_before_higher_rate") == 502_700_000


def test_full_basic_band_leaves_the_dividend_allowance_before_the_higher_rate():
    result = calculate(_input(existing_paye_income=600_000_000), PACK)
    assert result.get("dividend_before_higher_rate") == 5_000_000


def test_company_salary_reduces_profit_and_adds_income_tax():
    result = calculate(_input(director_salary=125_700_000), PACK)
    assert result.get("employer_national_insurance") == 11_355_000
    assert result.get("corporation_tax") == 191_180_425
    assert result.get("post_tax_profit") == 671_764_575
    assert result.get("available_dividend") == 671_764_575
    assert result.get("dividend_tax") == 257_151_860
    assert result.get("taper_income_tax") == 50_280_000
    assert result.get("net_dividend") == 364_332_715
    assert result.get("director_salary_income_tax") == 50_280_000
    assert result.get("director_salary_national_insurance") == 0
    assert result.get("director_salary_net") == 75_420_000


def test_reserves_add_to_the_available_dividend():
    result = calculate(_input(distributable_reserves=500_000_000), PACK)
    assert result.get("available_dividend") == 1_272_500_000
    assert result.get("dividend_taken") == 1_272_500_000
    assert result.get("remaining_reserves") == 0


def test_dividend_amount_can_be_tested_below_the_maximum():
    result = calculate(_input(dividend_amount=300_000_000), PACK)
    assert result.get("available_dividend") == 772_500_000
    assert result.get("dividend_taken") == 300_000_000
    assert result.get("personal_allowance") == 50_700_000
    assert result.get("dividend_tax") == 105_462_500
    assert result.get("taper_income_tax") == 30_000_000
    assert result.get("net_dividend") == 164_537_500
    assert result.get("remaining_reserves") == 472_500_000


def test_dividend_above_the_available_amount_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(dividend_amount=800_000_000), PACK)
    assert "available dividend" in excinfo.value.reason


@pytest.mark.parametrize(
    "overrides",
    [
        {"existing_paye_income": -1},
        {"company_profit": -1},
        {"director_salary": -1},
        {"distributable_reserves": -1},
        {"director_salary": 1_100_000_000},
        {"dividend_amount": -1},
    ],
)
def test_invalid_inputs_fail_closed(overrides):
    with pytest.raises(Unsupported):
        calculate(_input(**overrides), PACK)


def test_scottish_taxpayer_with_salary_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(scottish_taxpayer=True, director_salary=12_570_000), PACK)
    assert "Scottish" in excinfo.value.reason


def test_scottish_taxpayer_without_salary_is_allowed():
    result = calculate(_input(scottish_taxpayer=True), PACK)
    assert result.get("available_dividend") == 772_500_000


def test_result_id_is_stable_and_well_formed():
    first = calculate(_input(), PACK)
    second = calculate(_input(), PACK)
    assert first.result_id == second.result_id
    assert re.fullmatch(r"[0-9a-f]{12}", first.result_id)


def test_result_id_differs_for_different_inputs():
    first = calculate(_input(), PACK)
    second = calculate(_input(company_profit=900_000_000), PACK)
    assert first.result_id != second.result_id
