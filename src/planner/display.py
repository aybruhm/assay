import re
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


_EM_DASH = re.compile(r"\s*\u2014\s*")


def without_em_dashes(text: str) -> str:
    """
    Replace every em dash in model text with a comma.

    The prompts forbid em dashes. This catches any the model still writes, so
    no report or question reaches the user with one.

    Args:
        text: Text written by the model.

    Returns:
        The text with each em dash, and the spaces around it, replaced by ", ".
    """
    return _EM_DASH.sub(", ", text)
