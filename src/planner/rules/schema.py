from datetime import date
from re import compile as _compile
from typing import Literal

from pydantic import BaseModel, field_validator

# A decimal string with at most four places, e.g. "12570.00", "0.2000", "-1.50".
_VALUE = _compile(r"-?\d[\d,]*(?:\.\d{1,4})?")


class Rule(BaseModel):
    """One fact from a rule pack. Values are quoted decimal strings in the
    pack and are parsed into scaled ints by calculators via
    :func:`planner.core.utils.parse`."""

    id: str
    kind: Literal["amount", "rate", "flag", "band"]
    value: str
    effective_from: date
    source: str
    checked_on: date

    @field_validator("value")
    @classmethod
    def _value_must_be_a_decimal_string(cls, value: str) -> str:
        value = value.strip()
        if not _VALUE.fullmatch(value):
            raise ValueError(
                f"rule value {value!r} must be a decimal string with at most four places"
            )
        return value

    @field_validator("source")
    @classmethod
    def _source_must_be_a_url(cls, value: str) -> str:
        if not value.strip().startswith(("http://", "https://")):
            raise ValueError("rule source must be a URL")
        return value.strip()


class RulePack(BaseModel):
    """One country and tax year, validated against its YAML file."""

    jurisdiction: str
    tax_year: str
    starts: date
    ends: date
    version: int
    currency: str
    required_profile_fields: list[str] = []
    rules: list[Rule]

    @property
    def ref(self) -> RulePackRef:
        return RulePackRef(
            jurisdiction=self.jurisdiction,
            tax_year=self.tax_year,
            version=self.version,
        )


class RulePackRef(BaseModel):
    """A pointer to the pack a run used, recorded in state and results."""

    jurisdiction: str
    tax_year: str
    version: int
