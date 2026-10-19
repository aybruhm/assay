import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.income_tax import (
    IncomeTaxInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def _input(**overrides: object) -> IncomeTaxInput:
    values: dict[str, object] = {
        "salary": 0,
        "pension_income": 0,
        "rental_income": 0,
        "other_income": 0,
        "scottish_taxpayer": False,
    }
    values.update(overrides)
    return IncomeTaxInput(**values)


def test_salary_only_matches_take_home():
    result = calculate(_input(salary=450_000_000), PACK)
    assert result.calculator == "gb.income_tax"
    assert result.get("total_income") == 450_000_000
    assert result.get("personal_allowance") == 125_700_000
    assert result.get("taxable_income") == 324_300_000
    assert result.get("income_tax") == 64_860_000
    assert result.get("national_insurance") == 25_944_000
    assert result.get("net_income") == 359_196_000


def test_pension_income_is_taxed_but_has_no_national_insurance():
    result = calculate(_input(salary=450_000_000, pension_income=100_000_000), PACK)
    assert result.get("total_income") == 550_000_000
    assert result.get("income_tax") == 94_320_000
    assert result.get("national_insurance") == 25_944_000
    assert result.get("net_income") == 429_736_000


def test_rental_income_below_the_allowance_is_tax_free():
    result = calculate(_input(rental_income=120_000_000), PACK)
    assert result.get("total_income") == 120_000_000
    assert result.get("taxable_income") == 0
    assert result.get("income_tax") == 0
    assert result.get("national_insurance") == 0
    assert result.get("net_income") == 120_000_000


def test_high_income_uses_the_tapered_allowance():
    result = calculate(_input(salary=1_200_000_000), PACK)
    assert result.get("personal_allowance") == 25_700_000
    assert result.get("taxable_income") == 1_174_300_000
    assert result.get("income_tax") == 396_750_000
    assert result.get("national_insurance") == 44_106_000
    assert result.get("net_income") == 759_144_000


def test_negative_income_fails_closed():
    with pytest.raises(Unsupported):
        calculate(_input(rental_income=-1), PACK)


def test_scottish_taxpayer_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(_input(salary=450_000_000, scottish_taxpayer=True), PACK)
    assert "Scottish" in excinfo.value.reason
