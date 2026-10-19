import pytest

from planner.jurisdictions.gb.calculators.helpers import (
    capital_gains_tax,
    dividend_tax,
    income_tax,
    isa_tax,
    national_insurance,
    pension_contribution,
    personal_allowance_for,
    student_loan_repayment,
)

# Scaled ints: amounts x 10_000, rates are per-10_000 (20% == 2000).
PERSONAL_ALLOWANCE = 125_700_000
BASIC_RATE_LIMIT = 502_700_000
HIGHER_RATE_LIMIT = 1_251_400_000

INCOME_TAX_ARGS = dict(
    personal_allowance=PERSONAL_ALLOWANCE,
    basic_rate_limit=BASIC_RATE_LIMIT,
    higher_rate_limit=HIGHER_RATE_LIMIT,
    basic_rate=2000,
    higher_rate=4000,
    additional_rate=4500,
)


class TestIncomeTax:
    @pytest.mark.parametrize("gross", [0, -1, -10_000_000])
    def test_non_positive_gross_is_tax_free(self, gross):
        assert income_tax(gross, **INCOME_TAX_ARGS) == 0

    def test_within_personal_allowance_is_tax_free(self):
        assert income_tax(100_000_000, **INCOME_TAX_ARGS) == 0
        assert income_tax(PERSONAL_ALLOWANCE, **INCOME_TAX_ARGS) == 0

    def test_basic_band(self):
        # 45,000: 32,430 taxable at 20% == 6,486.
        assert income_tax(450_000_000, **INCOME_TAX_ARGS) == 64_860_000

    def test_basic_rate_limit(self):
        # 50,270: 37,700 taxable at 20% == 7,540.
        assert income_tax(BASIC_RATE_LIMIT, **INCOME_TAX_ARGS) == 75_400_000

    def test_higher_band(self):
        # 60,000: 7,540 + 9,730 at 40% == 11,432.
        assert income_tax(600_000_000, **INCOME_TAX_ARGS) == 114_320_000

    def test_additional_band(self):
        # 200,000: 7,540 + 29,948 + 74,860 at 45% == 71,175.
        assert income_tax(2_000_000_000, **INCOME_TAX_ARGS) == 711_750_000


class TestPersonalAllowance:
    TAPER_ARGS = dict(
        personal_allowance=PERSONAL_ALLOWANCE,
        taper_threshold=1_000_000_000,
        taper_rate=5000,
    )

    def test_income_below_the_threshold_keeps_the_full_allowance(self):
        assert (
            personal_allowance_for(850_000_000, **self.TAPER_ARGS) == PERSONAL_ALLOWANCE
        )
        assert (
            personal_allowance_for(1_000_000_000, **self.TAPER_ARGS)
            == PERSONAL_ALLOWANCE
        )

    def test_income_above_the_threshold_reduces_the_allowance(self):
        assert personal_allowance_for(1_200_000_000, **self.TAPER_ARGS) == 25_700_000

    def test_allowance_stops_at_zero(self):
        assert personal_allowance_for(1_251_400_000, **self.TAPER_ARGS) == 0
        assert personal_allowance_for(1_500_000_000, **self.TAPER_ARGS) == 0

    def test_tapered_allowance_keeps_the_band_widths(self):
        args = {
            **INCOME_TAX_ARGS,
            "personal_allowance": 25_700_000,
            "standard_personal_allowance": PERSONAL_ALLOWANCE,
        }
        assert income_tax(1_200_000_000, **args) == 396_750_000


class TestNationalInsurance:
    NATIONAL_INSURANCE_ARGS = dict(
        primary_threshold=PERSONAL_ALLOWANCE,
        upper_earnings_limit=BASIC_RATE_LIMIT,
        main_rate=800,
        additional_rate=200,
    )

    @pytest.mark.parametrize("gross", [0, -1, -5_000_000])
    def test_non_positive_gross_has_no_ni(self, gross):
        assert national_insurance(gross, **self.NATIONAL_INSURANCE_ARGS) == 0

    def test_up_to_primary_threshold_has_no_ni(self):
        assert national_insurance(5_000_000, **self.NATIONAL_INSURANCE_ARGS) == 0
        assert (
            national_insurance(PERSONAL_ALLOWANCE, **self.NATIONAL_INSURANCE_ARGS) == 0
        )

    def test_main_rate_band(self):
        # 45,000: 32,430 at 8% == 2,594.40.
        assert (
            national_insurance(450_000_000, **self.NATIONAL_INSURANCE_ARGS)
            == 25_944_000
        )

    def test_upper_earnings_limit(self):
        # 50,270: 37,700 at 8% == 3,016.
        assert (
            national_insurance(BASIC_RATE_LIMIT, **self.NATIONAL_INSURANCE_ARGS)
            == 30_160_000
        )

    def test_above_upper_earnings_limit(self):
        # 60,000: 3,016 + 9,730 at 2% == 3,210.60.
        assert (
            national_insurance(600_000_000, **self.NATIONAL_INSURANCE_ARGS)
            == 32_106_000
        )


class TestPensionContribution:
    @pytest.mark.parametrize("gross", [0, -1, -10_000_000])
    def test_non_positive_gross_has_no_contribution(self, gross):
        assert pension_contribution(gross, rate=500) == 0

    def test_contribution_is_gross_times_rate(self):
        assert pension_contribution(500_000_000, rate=500) == 25_000_000

    def test_zero_rate(self):
        assert pension_contribution(500_000_000, rate=0) == 0

    def test_full_rate(self):
        assert pension_contribution(500_000_000, rate=10_000) == 500_000_000

    def test_half_up_rounding(self):
        # 333.33 at 3.3% = 10.99989 -> 11.00 (1,099,989 scale, rounds up).
        assert pension_contribution(3_333_300, rate=330) == 109_999


class TestStudentLoanRepayment:
    @pytest.mark.parametrize("gross", [0, -1, -5_000_000])
    def test_non_positive_gross_has_no_repayment(self, gross):
        assert student_loan_repayment(gross, threshold=250_000_000, rate=900) == 0

    def test_at_or_below_threshold_has_no_repayment(self):
        assert student_loan_repayment(250_000_000, threshold=250_000_000, rate=900) == 0

    def test_above_threshold(self):
        # 30,000 with a 25,000 threshold: 5,000 at 9% == 450.
        assert (
            student_loan_repayment(300_000_000, threshold=250_000_000, rate=900)
            == 4_500_000
        )


class TestDividendTax:
    DIVIDEND_TAX_ARGS = dict(
        other_income=0,
        personal_allowance=0,
        allowance=5_000_000,
        basic_rate_limit=BASIC_RATE_LIMIT,
        higher_rate_limit=HIGHER_RATE_LIMIT,
        basic_rate=1075,
        higher_rate=3575,
        additional_rate=3935,
    )

    @pytest.mark.parametrize("dividends", [0, -1, -10_000_000])
    def test_non_positive_dividends_are_tax_free(self, dividends):
        assert dividend_tax(dividends, **self.DIVIDEND_TAX_ARGS) == 0

    def test_within_allowance_is_tax_free(self):
        assert dividend_tax(5_000_000, **self.DIVIDEND_TAX_ARGS) == 0

    def test_basic_band(self):
        # 3,000: 2,500 at 10.75% == 268.75.
        assert dividend_tax(30_000_000, **self.DIVIDEND_TAX_ARGS) == 2_687_500

    def test_basic_rate_limit(self):
        # 50,270: 49,770 at 10.75% == 5,350.2750 (scaled: 53,502,750).
        assert dividend_tax(BASIC_RATE_LIMIT, **self.DIVIDEND_TAX_ARGS) == 53_502_750


class TestCapitalGainsTax:
    CAPITAL_GAINS_TAX_ARGS = dict(
        other_income=0,
        personal_allowance=0,
        annual_exempt_amount=0,
        basic_rate_limit=BASIC_RATE_LIMIT,
        basic_rate=1000,
        higher_rate=2000,
    )

    @pytest.mark.parametrize("gains", [0, -1, -10_000_000])
    def test_non_positive_gains_are_tax_free(self, gains):
        assert capital_gains_tax(gains, **self.CAPITAL_GAINS_TAX_ARGS) == 0

    def test_gain_within_annual_exempt_amount_is_tax_free(self):
        args = {**self.CAPITAL_GAINS_TAX_ARGS, "annual_exempt_amount": 3_000_000}
        assert capital_gains_tax(3_000_000, **args) == 0

    def test_basic_band(self):
        assert (
            capital_gains_tax(100_000_000, **self.CAPITAL_GAINS_TAX_ARGS) == 10_000_000
        )

    def test_basic_rate_limit(self):
        assert (
            capital_gains_tax(BASIC_RATE_LIMIT, **self.CAPITAL_GAINS_TAX_ARGS)
            == 50_270_000
        )

    def test_higher_band(self):
        # 60,000: 50,270 + 9,730 at 20% == 69,730.
        assert (
            capital_gains_tax(600_000_000, **self.CAPITAL_GAINS_TAX_ARGS) == 69_730_000
        )

    def test_other_income_uses_up_the_basic_band(self):
        args = {
            **self.CAPITAL_GAINS_TAX_ARGS,
            "other_income": 400_000_000,
            "personal_allowance": PERSONAL_ALLOWANCE,
        }
        # Taxable income is 27,430, leaving 10,270 of the basic band.
        # 10,270 at 10% and 9,730 at 20% == 2,973.
        assert capital_gains_tax(200_000_000, **args) == 29_730_000


class TestIsaTax:
    @pytest.mark.parametrize("isa_income", [0, -1, 100_000_000])
    def test_isa_income_is_always_tax_free(self, isa_income):
        assert isa_tax(isa_income) == 0
