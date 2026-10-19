from planner.core import utils as fp


def parse_amount(raw: str) -> int:
    """
    Parse an amount written by a user.

    Args:
        raw: The amount, for example `45,000` or `£45,000.50`.

    Returns:
        The amount at `SCALE`.

    Raises:
        ValueError: If the text is not an amount.
    """
    return fp.parse(raw.strip().lstrip("£€$₦"))


def parse_rate(raw: str) -> int:
    """
    Parse a rate written as a decimal or a percentage.

    Args:
        raw: The rate, for example `6%`, `6`, or `0.06`.

    Returns:
        The rate at `SCALE`.

    Raises:
        ValueError: If the rate is not between 0 and 1.
    """
    text = raw.strip().replace("%", "")
    value = fp.parse(text)
    if "%" in raw or value > fp.SCALE:
        value //= 100
    if not 0 <= value <= fp.SCALE:
        raise ValueError(f"not a rate: {raw!r}")
    return value


def parse_years(raw: str | int) -> int:
    """
    Parse a number of years.

    Args:
        raw: The number of years, for example `10`, `10 years`, or `10 year`.

    Returns:
        The number of years.

    Raises:
        ValueError: If the value is not between 1 and 100.
    """
    if isinstance(raw, int):
        years = raw
    else:
        text = raw.strip().lower().removesuffix("years").removesuffix("year").strip()
        years = int(text)
    if not 1 <= years <= 100:
        raise ValueError(f"not a number of years: {raw!r}")
    return years
