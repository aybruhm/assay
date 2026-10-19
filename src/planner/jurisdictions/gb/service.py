from typing import ClassVar

from planner.jurisdictions.base import Calculator
from planner.jurisdictions.gb.calculators.director_pay import (
    DirectorPayInput,
)
from planner.jurisdictions.gb.calculators.director_pay import (
    calculate as director_pay,
)
from planner.jurisdictions.gb.calculators.dividend_capacity import (
    DividendCapacityInput,
)
from planner.jurisdictions.gb.calculators.dividend_capacity import (
    calculate as dividend_capacity,
)
from planner.jurisdictions.gb.calculators.income_tax import (
    IncomeTaxInput,
)
from planner.jurisdictions.gb.calculators.income_tax import (
    calculate as income_tax,
)
from planner.jurisdictions.gb.calculators.isa_vs_general import (
    IsaVsGeneralInput,
)
from planner.jurisdictions.gb.calculators.isa_vs_general import (
    calculate as isa_vs_general,
)
from planner.jurisdictions.gb.calculators.pension import (
    PensionInput,
)
from planner.jurisdictions.gb.calculators.pension import (
    calculate as pension,
)
from planner.jurisdictions.gb.calculators.student_loan import (
    StudentLoanInput,
)
from planner.jurisdictions.gb.calculators.student_loan import (
    calculate as student_loan,
)
from planner.jurisdictions.gb.calculators.take_home import (
    TakeHomeInput,
)
from planner.jurisdictions.gb.calculators.take_home import (
    calculate as take_home,
)


class _GB:
    code = "GB"
    currency = "GBP"

    # Mutable so tests can substitute a counting wrapper (crash/resume test).
    calculators: ClassVar[dict[str, Calculator]] = {
        "gb.take_home": (TakeHomeInput, take_home),
        "gb.pension": (PensionInput, pension),
        "gb.director_pay": (DirectorPayInput, director_pay),
        "gb.dividend_capacity": (DividendCapacityInput, dividend_capacity),
        "gb.income_tax": (IncomeTaxInput, income_tax),
        "gb.isa_vs_general": (IsaVsGeneralInput, isa_vs_general),
        "gb.student_loan": (StudentLoanInput, student_loan),
    }

    def calculator(self, template: str) -> Calculator:
        return self.calculators[template]


GB = _GB()
