from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel

from planner.core.types import CalcResult
from planner.rules.schema import RulePack

Calculator = tuple[type[BaseModel], Callable[[Any, RulePack], CalcResult]]


class Jurisdiction(Protocol):
    """Contract every country package implements; the graph knows only this.

    Adding a country means writing one package (calculators and rule packs)
    and one line in the registry. The graph never changes.
    """

    code: str  # ISO 3166-1 alpha-2
    currency: str  # ISO 4217; amounts stay plain ints at fp.SCALE

    def calculator(self, template: str) -> Calculator: ...
