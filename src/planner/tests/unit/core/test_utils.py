import pytest

from planner.core import utils as fp


class TestParse:
    def test_plain_integer(self):
        assert fp.parse("45000") == 450_000_000

    def test_thousands_separators(self):
        assert fp.parse("45,000") == 450_000_000

    def test_two_decimals(self):
        assert fp.parse("45000.50") == 450_005_000

    def test_four_decimals(self):
        assert fp.parse("0.0001") == 1

    def test_pads_short_decimals(self):
        assert fp.parse("1.5") == 15_000

    def test_negative(self):
        assert fp.parse("-1.50") == -15_000

    @pytest.mark.parametrize("raw", ["£45,000", "€1.50", "$1.50", "₦45,000"])
    def test_leading_currency_symbols(self, raw):
        assert fp.parse(raw) == fp.parse(raw[1:])

    def test_rate_strings(self):
        assert fp.parse("0.2000") == 2000

    @pytest.mark.parametrize("raw", ["1.00005", "abc", "", "12,34x"])
    def test_rejects_malformed_amounts(self, raw):
        with pytest.raises(ValueError):
            fp.parse(raw)

    def test_rejects_more_than_four_decimals(self):
        # Rounding must be explicit and named, never implied by truncation.
        with pytest.raises(ValueError):
            fp.parse("1.00005")


class TestQuantize:
    def test_half_up_positive(self):
        assert fp.quantize(1_234_565, fp.PENNY) == 1_234_600  # 123.4565 -> 123.46

    def test_half_up_negative(self):
        assert fp.quantize(-1_234_565, fp.PENNY) == -1_234_600

    def test_tie_rounds_away_from_zero(self):
        assert fp.quantize(15_000, 10_000) == 20_000
        assert fp.quantize(-15_000, 10_000) == -20_000

    def test_aligned_amount_is_unchanged(self):
        assert fp.quantize(450_000_000, fp.PENNY) == 450_000_000

    def test_rejects_unit_that_does_not_divide_scale(self):
        with pytest.raises(ValueError):
            fp.quantize(100, 3)


class TestMul:
    def test_twenty_percent(self):
        assert fp.mul(324_300_000, 2000) == 64_860_000

    def test_half_up(self):
        # 0.0001 x 0.5 = 0.00005 rounds up to 0.0001.
        assert fp.mul(1, 5000) == 1

    def test_negative_rounds_away_from_zero(self):
        assert fp.mul(-1, 5000) == -1


class TestFormatAmount:
    @pytest.mark.parametrize(
        ("amount", "expected"),
        [
            (1_423_823_234, "142,382.32"),
            (1_234_565, "123.46"),
            (-15_000, "-1.50"),
            (0, "0.00"),
        ],
    )
    def test_display_vectors(self, amount, expected):
        assert fp.format_amount(amount) == expected
