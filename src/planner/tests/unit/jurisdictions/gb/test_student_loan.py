import re

import pytest

from planner.core.types import Unsupported
from planner.jurisdictions.gb.calculators.student_loan import (
    StudentLoanInput,
    calculate,
)
from planner.rules.loader import load_pack

PACK = load_pack("GB", "2026-27")


def test_plan_two_repayment():
    result = calculate(StudentLoanInput(gross_annual=450_000_000, plan="plan2"), PACK)
    assert result.calculator == "gb.student_loan"
    assert result.get("threshold") == 293_850_000
    assert result.get("repayment_rate") == 900
    assert result.get("student_loan_repayment") == 14_053_500


def test_plan_one_repayment():
    result = calculate(StudentLoanInput(gross_annual=450_000_000, plan="plan1"), PACK)
    assert result.get("threshold") == 269_000_000
    assert result.get("student_loan_repayment") == 16_290_000


def test_postgraduate_repayment():
    result = calculate(
        StudentLoanInput(gross_annual=450_000_000, plan="postgraduate"), PACK
    )
    assert result.get("threshold") == 210_000_000
    assert result.get("repayment_rate") == 600
    assert result.get("student_loan_repayment") == 14_400_000


def test_income_below_the_threshold_has_no_repayment():
    result = calculate(StudentLoanInput(gross_annual=200_000_000, plan="plan2"), PACK)
    assert result.get("student_loan_repayment") == 0


def test_negative_income_fails_closed():
    with pytest.raises(Unsupported):
        calculate(StudentLoanInput(gross_annual=-1, plan="plan2"), PACK)


def test_result_id_is_stable_and_well_formed():
    calculator_input = StudentLoanInput(gross_annual=450_000_000, plan="plan2")
    first = calculate(calculator_input, PACK)
    second = calculate(calculator_input, PACK)
    assert first.result_id == second.result_id
    assert re.fullmatch(r"[0-9a-f]{12}", first.result_id)
