from dataclasses import dataclass, field
from typing import Literal


class Unsupported(Exception):
    """A calculator cannot answer this input; carries the user-facing reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CalcLine:
    """One output figure of a calculation, with the rules that produced it."""

    key: str
    amount: int  # at planner.core.utils.SCALE
    rule_ids: list[str] = field(default_factory=list)
    display_as: Literal["money", "rate", "text"] = "money"
    source: str | None = None


@dataclass(frozen=True)
class CalcResult:
    """A calculator call and its outputs. The report cites these by result_id."""

    result_id: str
    calculator: str
    calculator_version: str
    inputs: dict[str, int | str | bool | None]
    lines: list[CalcLine]

    def get(self, key: str) -> int:
        """
        Return the amount of the named output line.

        Args:
            key: The line key, for example `net_pay`.

        Returns:
            The amount at `planner.core.utils.SCALE`.

        Raises:
            KeyError: If no line has that key.
        """
        for line in self.lines:
            if line.key == key:
                return line.amount
        raise KeyError(key)
