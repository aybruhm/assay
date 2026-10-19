import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.director_pay import (
    DirectorPayInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def test_salary_and_dividends_against_paye():
    result = calculate(
        DirectorPayInput(
            company_profit=1_000_000_000,
            director_salary=125_700_000,
            scottish_taxpayer=False,
        ),
        PACK,
    )
    assert result.calculator == "gb.director_pay"
    assert result.get("employer_national_insurance") == 11_355_000
    assert result.get("corporation_tax") == 191_180_425
    assert result.get("dividends") == 671_764_575
    assert result.get("employee_national_insurance") == 0
    assert result.get("income_tax") == 0
    assert result.get("dividend_tax") == 145_368_336
    assert result.get("net_pay") == 652_096_239
    assert result.get("paye_gross_salary") == 876_086_957
    assert result.get("paye_employer_national_insurance") == 123_913_044
    assert result.get("paye_employee_national_insurance") == 37_627_739
    assert result.get("paye_income_tax") == 224_754_783
    assert result.get("paye_net_pay") == 613_704_435
    assert result.get("difference") == 38_391_804


def test_salary_above_profit_fails_closed():
    with pytest.raises(Unsupported):
        calculate(
            DirectorPayInput(
                company_profit=1_000_000_000,
                director_salary=2_000_000_000,
                scottish_taxpayer=False,
            ),
            PACK,
        )


def test_scottish_taxpayer_fails_closed():
    with pytest.raises(Unsupported) as excinfo:
        calculate(
            DirectorPayInput(
                company_profit=1_000_000_000,
                director_salary=125_700_000,
                scottish_taxpayer=True,
            ),
            PACK,
        )
    assert "Scottish" in excinfo.value.reason
