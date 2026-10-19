from datetime import date

import pytest
from pydantic import ValidationError

from planner.rules.loader import NoRulePack, load_pack, load_ref, resolve
from planner.rules.schema import RulePackRef


class TestResolve:
    def test_pack_covering_the_planning_date(self):
        pack = resolve("GB", date(2026, 10, 1))
        assert pack.jurisdiction == "GB"
        assert pack.tax_year == "2026-27"
        assert pack.version == 1
        assert pack.currency == "GBP"

    def test_date_outside_all_windows_fails(self):
        with pytest.raises(NoRulePack):
            resolve("GB", date(2027, 6, 1))

    def test_unknown_country_fails(self):
        with pytest.raises(NoRulePack):
            resolve("FR", date(2026, 10, 1))


class TestLoadPack:
    def test_missing_pack_fails(self):
        with pytest.raises(NoRulePack):
            load_pack("GB", "1999-00")

    def test_pack_validated_against_schema(self, tmp_path, monkeypatch):
        (tmp_path / "gb").mkdir()
        bad = tmp_path / "gb" / "2026-27.yaml"
        bad.write_text(
            "jurisdiction: GB\n"
            "tax_year: '2026-27'\n"
            "starts: 2026-04-06\n"
            "ends: 2027-04-05\n"
            "version: 1\n"
            "currency: GBP\n"
            "rules:\n"
            "  - id: gb.income_tax.personal_allowance\n"
            "    kind: amount\n"
            "    value: '12570.00'\n"
            "    effective_from: 2026-04-06\n"
            "    source: not-a-url\n"
            "    checked_on: 2026-09-27\n"
        )
        monkeypatch.setenv("PLANNER_RULES_DIR", str(tmp_path))
        with pytest.raises(ValidationError):
            load_pack("GB", "2026-27")


class TestLoadRef:
    def test_matching_version_loads(self):
        ref = RulePackRef(jurisdiction="GB", tax_year="2026-27", version=1)
        assert load_ref(ref).tax_year == "2026-27"

    def test_version_mismatch_fails_loudly(self):
        ref = RulePackRef(jurisdiction="GB", tax_year="2026-27", version=99)
        with pytest.raises(NoRulePack, match="changed since the run started"):
            load_ref(ref)
