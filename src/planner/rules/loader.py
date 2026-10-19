import os
from datetime import date
from pathlib import Path

import yaml

from planner.rules.schema import RulePack, RulePackRef

# assay/rules; overridable per call via PLANNER_RULES_DIR (tests, deployments).
_DEFAULT_RULES_DIR = Path(__file__).resolve().parents[3] / "rules"


class NoRulePack(Exception):
    """No pack matches the requested country, tax year or planning date."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def _rules_dir() -> Path:
    return Path(os.environ.get("PLANNER_RULES_DIR", _DEFAULT_RULES_DIR))


def _path(country: str, tax_year: str) -> Path:
    return _rules_dir() / country.lower() / f"{tax_year}.yaml"


def load_pack(country: str, tax_year: str) -> RulePack:
    path = _path(country, tax_year)
    if not path.exists():
        raise NoRulePack(f"no rule pack for {country} {tax_year}")
    return RulePack.model_validate(yaml.safe_load(path.read_text()))


def resolve(country: str, planning_date: date) -> RulePack:
    """
    Return the rule pack for a country and planning date.

    Args:
        country: The ISO 3166-1 alpha-2 country code.
        planning_date: The date the plan is for.

    Returns:
        The pack whose `starts` and `ends` contain the date.

    Raises:
        NoRulePack: If the country has no packs or none covers the date.
    """
    directory = _rules_dir() / country.lower()
    if not directory.is_dir():
        raise NoRulePack(f"no rule packs for {country}")
    for path in sorted(directory.glob("*.yaml")):
        pack = load_pack(country, path.stem)
        if pack.starts <= planning_date <= pack.ends:
            return pack
    raise NoRulePack(f"no rule pack for {country} covers {planning_date}")


def load_ref(ref: RulePackRef) -> RulePack:
    """
    Load the rule pack a reference points at.

    Args:
        ref: The jurisdiction, tax year, and version recorded by the run.

    Returns:
        The current pack for that jurisdiction and tax year.

    Raises:
        NoRulePack: If the pack is missing or its version changed since the
            run started.
    """
    pack = load_pack(ref.jurisdiction, ref.tax_year)
    if pack.version != ref.version:
        raise NoRulePack(
            f"rule pack {ref.jurisdiction} {ref.tax_year} changed since the run "
            f"started (recorded version {ref.version}, current version {pack.version})"
        )
    return pack
