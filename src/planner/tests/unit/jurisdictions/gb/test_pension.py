import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.pension import PensionInput, calculate
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def test_six_percent_contribution_reduces_taxable_pay_and_net_pay():
    result = calculate(
        PensionInput(
            gross_annual=850_000_000,
            scottish_taxpayer=False,
            pension_rate=600,
        ),
        PACK,
    )
    assert result.calculator == "gb.pension"
    assert result.get("gross_annual") == 850_000_000
    assert result.get("pension_contribution") == 51_000_000
    assert result.get("taxable_pay") == 799_000_000
    assert result.get("income_tax") == 193_920_000
    assert result.get("national_insurance") == 36_086_000
    assert result.get("net_pay") == 568_994_000


def test_zero_rate_fails_closed():
    with pytest.raises(Unsupported):
        calculate(
            PensionInput(
                gross_annual=850_000_000,
                scottish_taxpayer=False,
                pension_rate=0,
            ),
            PACK,
        )


def test_scottish_taxpayer_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(
            PensionInput(
                gross_annual=850_000_000,
                scottish_taxpayer=True,
                pension_rate=600,
            ),
            PACK,
        )
    assert "Scottish" in excinfo.value.reason
