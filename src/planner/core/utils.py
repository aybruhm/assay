from enum import Enum

SCALE = 10_000
PENNY = 100


class Rounding(Enum):
    HALF_UP = "half_up"


def _round_half_up(numerator: int, denominator: int) -> int:
    """
    Round a ratio to the nearest integer, with ties away from zero.

    Args:
        numerator: The top of the ratio.
        denominator: The bottom of the ratio.

    Returns:
        The rounded integer.

    Raises:
        ValueError: If `denominator` is not positive.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if 2 * remainder >= denominator:
        quotient += 1
    return sign * quotient


def parse(raw: str) -> int:
    """
    Parse a decimal amount string into a scaled integer.

    Accepts thousands separators, an optional leading currency symbol, and
    up to four decimal places.

    Args:
        raw: The amount as written, for example `45,000` or `£45,000.50`.

    Returns:
        The amount at `SCALE`.

    Raises:
        ValueError: If the text is not an amount or has more than four
            decimal places.
    """
    cleaned = raw.strip().lstrip("£€$₦").replace(",", "")
    if not cleaned:
        raise ValueError(f"not an amount: {raw!r}")

    sign = 1
    if cleaned.startswith("-"):
        sign, cleaned = -1, cleaned[1:]

    if "." in cleaned:
        whole, _, frac = cleaned.partition(".")
        if not whole.isdigit() or not frac.isdigit():
            raise ValueError(f"not an amount: {raw!r}")
        if len(frac) > 4:
            raise ValueError(f"more than four decimal places: {raw!r}")

        frac = frac.ljust(4, "0")
    else:
        if not cleaned.isdigit():
            raise ValueError(f"not an amount: {raw!r}")

        whole, frac = cleaned, "0000"
    return sign * (int(whole) * SCALE + int(frac))


def quantize(amount: int, unit: int, rounding: Rounding = Rounding.HALF_UP) -> int:
    """
    Round an amount to the nearest multiple of a unit.

    Args:
        amount: The amount at `SCALE`.
        unit: The rounding unit. It must divide `SCALE`, for example `PENNY`.
        rounding: The named rounding rule.

    Returns:
        The rounded amount at `SCALE`.

    Raises:
        ValueError: If `unit` is not positive or does not divide `SCALE`.
        NotImplementedError: If `rounding` is not supported.
    """
    if unit <= 0 or SCALE % unit:
        raise ValueError(f"unit {unit} must be positive and divide SCALE")
    if rounding is not Rounding.HALF_UP:
        raise NotImplementedError(rounding)
    return _round_half_up(amount, unit) * unit


def mul(amount: int, rate: int, rounding: Rounding = Rounding.HALF_UP) -> int:
    """
    Multiply an amount by a scaled rate.

    Args:
        amount: The amount at `SCALE`.
        rate: The rate at `SCALE`, for example `2000` for 20%.
        rounding: The named rounding rule.

    Returns:
        The product at `SCALE`.

    Raises:
        NotImplementedError: If `rounding` is not supported.
    """
    if rounding is not Rounding.HALF_UP:
        raise NotImplementedError(rounding)
    return _round_half_up(amount * rate, SCALE)


def divide(numerator: int, denominator: int) -> int:
    """
    Divide two integers, rounding half up.

    Args:
        numerator: The top of the ratio.
        denominator: The bottom of the ratio.

    Returns:
        The rounded integer.

    Raises:
        ValueError: If `denominator` is not positive.
    """
    return _round_half_up(numerator, denominator)


def format_amount(amount: int) -> str:
    """
    Format an amount as a grouped decimal string to the penny.

    Rounding to the penny is explicit, so a four-decimal amount is never
    silently truncated.

    Args:
        amount: The amount at `SCALE`.

    Returns:
        The amount with thousands separators and two decimal places.
    """
    penny = quantize(amount, PENNY, Rounding.HALF_UP)
    sign = "-" if penny < 0 else ""
    whole, frac = divmod(abs(penny), SCALE)
    return f"{sign}{whole:,}.{frac // PENNY:02d}"
