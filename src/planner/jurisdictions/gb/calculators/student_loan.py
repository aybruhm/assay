import hashlib
import json
from typing import Literal

from pydantic import BaseModel, StrictInt

from planner.core import utils as fp
from planner.core.types import CalcLine, CalcResult, Unsupported
from planner.jurisdictions.gb.calculators import helpers
from planner.rules.schema import RulePack

CALCULATOR_VERSION = "1"

StudentLoanPlan = Literal["plan1", "plan2", "plan4", "plan5", "postgraduate"]

PLAN_RULES: dict[StudentLoanPlan, tuple[str, str]] = {
    "plan1": ("gb.student_loan.plan1_threshold", "gb.student_loan.plan1_rate"),
    "plan2": ("gb.student_loan.plan2_threshold", "gb.student_loan.plan2_rate"),
    "plan4": ("gb.student_loan.plan4_threshold", "gb.student_loan.plan4_rate"),
    "plan5": ("gb.student_loan.plan5_threshold", "gb.student_loan.plan5_rate"),
    "postgraduate": (
        "gb.student_loan.postgraduate_threshold",
        "gb.student_loan.postgraduate_rate",
    ),
}


class StudentLoanInput(BaseModel):
    gross_annual: StrictInt  # at fp.SCALE
    plan: StudentLoanPlan


def _values(pack: RulePack) -> dict[str, int]:
    return {rule.id: fp.parse(rule.value) for rule in pack.rules}


def _result_id(calculator_input: StudentLoanInput) -> str:
    """
    Return a stable identifier for a calculator input.

    Args:
        calculator_input: The calculator input.

    Returns:
        The first 12 hex characters of the SHA-256 hash.
    """
    blob = json.dumps(
        [
            "gb.student_loan",
            CALCULATOR_VERSION,
            {
                "gross_annual": calculator_input.gross_annual,
                "plan": calculator_input.plan,
            },
        ],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calculate(calculator_input: StudentLoanInput, pack: RulePack) -> CalcResult:
    if calculator_input.gross_annual < 0:
        raise Unsupported("gross annual income cannot be negative")

    values = _values(pack)
    threshold_rule, rate_rule = PLAN_RULES[calculator_input.plan]
    threshold = values[threshold_rule]
    rate = values[rate_rule]
    repayment = helpers.student_loan_repayment(
        calculator_input.gross_annual,
        threshold=threshold,
        rate=rate,
    )

    return CalcResult(
        result_id=_result_id(calculator_input),
        calculator="gb.student_loan",
        calculator_version=CALCULATOR_VERSION,
        inputs={
            "gross_annual": calculator_input.gross_annual,
            "plan": calculator_input.plan,
        },
        lines=[
            CalcLine(key="gross_annual", amount=calculator_input.gross_annual),
            CalcLine(key="threshold", amount=threshold, rule_ids=[threshold_rule]),
            CalcLine(
                key="repayment_rate",
                amount=rate,
                rule_ids=[rate_rule],
                display_as="rate",
            ),
            CalcLine(
                key="student_loan_repayment",
                amount=repayment,
                rule_ids=[threshold_rule, rate_rule],
            ),
        ],
    )
