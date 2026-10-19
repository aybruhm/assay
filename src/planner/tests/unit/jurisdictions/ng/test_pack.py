from datetime import date

import pytest

from planner.rules.loader import NoRulePack, resolve


def test_calendar_year_pack_resolves_by_date():
    pack = resolve("NG", date(2026, 7, 15))
    assert pack.jurisdiction == "NG"
    assert pack.tax_year == "2026"
    assert pack.currency == "NGN"
    assert pack.starts == date(2026, 1, 1)
    assert pack.ends == date(2026, 12, 31)


def test_date_outside_calendar_year_fails():
    with pytest.raises(NoRulePack):
        resolve("NG", date(2025, 12, 31))


def test_ng_and_gb_packs_are_independent():
    # The same planning date resolves to a different pack per country.
    assert resolve("GB", date(2026, 10, 1)).currency == "GBP"
    assert resolve("NG", date(2026, 10, 1)).currency == "NGN"
