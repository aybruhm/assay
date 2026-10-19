import pytest

from planner.jurisdictions.gb import GB
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
from planner.jurisdictions.gb.calculators.take_home import TakeHomeInput as GbInput
from planner.jurisdictions.gb.calculators.take_home import calculate as gb_calculate
from planner.jurisdictions.ng import NG
from planner.jurisdictions.ng.calculators.take_home import TakeHomeInput as NgInput
from planner.jurisdictions.ng.calculators.take_home import calculate as ng_calculate
from planner.jurisdictions.registry import REGISTRY


def test_registry_holds_gb_and_ng():
    assert REGISTRY["GB"].code == "GB"
    assert REGISTRY["GB"].currency == "GBP"
    assert REGISTRY["NG"].code == "NG"
    assert REGISTRY["NG"].currency == "NGN"


def test_gb_exposes_its_calculators():
    assert GB.calculator("gb.take_home") == (GbInput, gb_calculate)
    assert GB.calculator("gb.pension") == (PensionInput, pension)
    assert GB.calculator("gb.director_pay") == (DirectorPayInput, director_pay)
    assert GB.calculator("gb.dividend_capacity") == (
        DividendCapacityInput,
        dividend_capacity,
    )
    assert GB.calculator("gb.income_tax") == (IncomeTaxInput, income_tax)
    assert GB.calculator("gb.isa_vs_general") == (
        IsaVsGeneralInput,
        isa_vs_general,
    )
    assert GB.calculator("gb.student_loan") == (StudentLoanInput, student_loan)


def test_ng_exposes_the_take_home_calculator():
    assert NG.calculator("ng.take_home") == (NgInput, ng_calculate)


def test_unknown_template_fails():
    with pytest.raises(KeyError):
        GB.calculator("gb.nope")
    with pytest.raises(KeyError):
        NG.calculator("ng.nope")


def test_required_fields_come_from_the_rule_packs():
    from planner.rules.loader import load_pack

    assert "scottish_taxpayer" in load_pack("GB", "2026-27").required_profile_fields
    assert "scottish_taxpayer" not in load_pack("NG", "2026").required_profile_fields


def test_registry_values_satisfy_the_contract():
    for jurisdiction in REGISTRY.values():
        assert jurisdiction.code
        assert jurisdiction.currency
