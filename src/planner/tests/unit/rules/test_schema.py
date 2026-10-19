import pytest
from pydantic import ValidationError

from planner.rules.schema import RulePack


def _pack(rules: list[dict[str, object]]) -> dict[str, object]:
    return {
        "jurisdiction": "GB",
        "tax_year": "2026-27",
        "starts": "2026-04-06",
        "ends": "2027-04-05",
        "version": 1,
        "currency": "GBP",
        "rules": rules,
    }


def _rule(**overrides: object) -> dict[str, object]:
    rule: dict[str, object] = {
        "id": "gb.income_tax.personal_allowance",
        "kind": "amount",
        "value": "12570.00",
        "effective_from": "2026-04-06",
        "source": "https://www.gov.uk/income-tax-rates",
        "checked_on": "2026-09-27",
    }
    rule.update(overrides)
    return rule


def test_valid_pack_parses() -> None:
    pack = RulePack.model_validate(_pack([_rule()]))
    assert pack.ref.jurisdiction == "GB"
    assert pack.ref.version == 1


def test_missing_source_fails():
    with pytest.raises(ValidationError):
        RulePack.model_validate(_pack([_rule(source="")]))


def test_non_url_source_fails():
    with pytest.raises(ValidationError):
        RulePack.model_validate(_pack([_rule(source="gov.uk/page")]))


def test_malformed_value_fails():
    with pytest.raises(ValidationError):
        RulePack.model_validate(_pack([_rule(value="about twelve thousand")]))


def test_value_with_more_than_four_decimals_fails():
    with pytest.raises(ValidationError):
        RulePack.model_validate(_pack([_rule(value="12570.00001")]))
