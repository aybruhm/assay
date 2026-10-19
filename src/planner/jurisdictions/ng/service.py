from typing import ClassVar

from planner.jurisdictions.base import Calculator
from planner.jurisdictions.ng.calculators.take_home import (
    TakeHomeInput,
)
from planner.jurisdictions.ng.calculators.take_home import (
    calculate as take_home,
)


class _NG:
    code = "NG"
    currency = "NGN"

    # Mutable so tests can substitute a counting wrapper.
    calculators: ClassVar[dict[str, Calculator]] = {
        "ng.take_home": (TakeHomeInput, take_home)
    }

    def calculator(self, template: str) -> Calculator:
        return self.calculators[template]


NG = _NG()
