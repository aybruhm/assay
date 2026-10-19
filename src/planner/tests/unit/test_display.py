import pytest

from planner.display import display


@pytest.mark.parametrize(
    ("amount", "currency", "shown"),
    [
        (1_423_823_234, "GBP", "£142,382.32"),
        (1_234_565, "GBP", "£123.46"),
        (-15_000, "GBP", "£-1.50"),
        (0, "EUR", "€0.00"),
        (450_000_000, "GBP", "£45,000.00"),
    ],
)
def test_display_vectors(amount, currency, shown):
    assert display(amount, currency) == shown


def test_rate_is_shown_as_a_percentage():
    assert display(2000, "GBP", "rate") == "20.00%"
    assert display(1075, "GBP", "rate") == "10.75%"


def test_text_is_shown_as_a_boolean():
    assert display(1, "GBP", "text") == "true"
    assert display(0, "GBP", "text") == "false"
