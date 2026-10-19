from typing import Literal

from planner.core import utils as fp

SYMBOLS = {"GBP": "£", "EUR": "€", "NGN": "₦", "USD": "$"}


def display(
    amount: int,
    currency: str,
    display_as: Literal["money", "rate", "text"] = "money",
) -> str:
    """
    Format a figure for the report.

    This is the single definition of how a figure looks. Narration copies
    the output and the validator recomputes it, so both sides agree.

    Args:
        amount: The amount at `planner.core.utils.SCALE`.
        currency: The ISO 4217 currency code.
        display_as: The kind of figure: money, rate or text.

    Returns:
        The formatted figure.
    """
    if display_as == "rate":
        percent = fp.mul(amount, 100 * fp.SCALE)
        return f"{fp.format_amount(percent)}%"
    if display_as == "text":
        return "true" if amount else "false"
    return SYMBOLS[currency] + fp.format_amount(amount)
