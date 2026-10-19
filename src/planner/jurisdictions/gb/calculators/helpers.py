from planner.core import utils as fp


def personal_allowance_for(
    income: int,
    *,
    personal_allowance: int,
    taper_threshold: int,
    taper_rate: int,
) -> int:
    """
    Compute the personal allowance after the income taper.

    Args:
        income: The total income at `SCALE`.
        personal_allowance: The standard personal allowance at `SCALE`.
        taper_threshold: The income where the taper starts, at `SCALE`.
        taper_rate: The fraction of income above the threshold that reduces
            the allowance, at `SCALE`.

    Returns:
        The tapered allowance at `SCALE`, never below zero.
    """
    if income <= taper_threshold:
        return personal_allowance
    reduction = fp.mul(income - taper_threshold, taper_rate)
    return max(personal_allowance - reduction, 0)


def income_tax(
    gross: int,
    *,
    personal_allowance: int,
    standard_personal_allowance: int | None = None,
    basic_rate_limit: int,
    higher_rate_limit: int,
    basic_rate: int,
    higher_rate: int,
    additional_rate: int,
) -> int:
    """
    Compute income tax on a gross amount.

    Args:
        gross: The gross amount at `SCALE`.
        personal_allowance: The tax-free allowance at `SCALE`.
        standard_personal_allowance: The standard allowance before any taper,
            at `SCALE`. Defaults to `personal_allowance`.
        basic_rate_limit: The upper limit of the basic band at `SCALE`.
        higher_rate_limit: The upper limit of the higher band at `SCALE`.
        basic_rate: The basic rate at `SCALE`.
        higher_rate: The higher rate at `SCALE`.
        additional_rate: The additional rate at `SCALE`.

    Returns:
        The income tax at `SCALE`.
    """
    if gross <= 0:
        return 0

    standard = (
        personal_allowance
        if standard_personal_allowance is None
        else standard_personal_allowance
    )
    basic_band = max(basic_rate_limit - standard, 0)
    higher_band = max(higher_rate_limit - basic_rate_limit, 0)
    remaining = max(gross - personal_allowance, 0)
    tax = 0

    if remaining > 0:
        basic = min(remaining, basic_band)
        tax += fp.mul(basic, basic_rate)
        remaining -= basic

    if remaining > 0:
        higher = min(remaining, higher_band)
        tax += fp.mul(higher, higher_rate)
        remaining -= higher

    if remaining > 0:
        tax += fp.mul(remaining, additional_rate)

    return tax


def national_insurance(
    gross: int,
    *,
    primary_threshold: int,
    upper_earnings_limit: int,
    main_rate: int,
    additional_rate: int,
) -> int:
    """
    Compute employee National Insurance.

    Args:
        gross: The gross amount at `SCALE`.
        primary_threshold: The threshold where contributions start, at
            `SCALE`.
        upper_earnings_limit: The limit where the additional rate starts,
            at `SCALE`.
        main_rate: The main rate at `SCALE`.
        additional_rate: The additional rate at `SCALE`.

    Returns:
        The National Insurance contribution at `SCALE`.
    """
    if gross <= 0:
        return 0

    remaining = max(gross - primary_threshold, 0)
    contribution = 0

    if remaining > 0:
        main = min(remaining, upper_earnings_limit - primary_threshold)
        contribution += fp.mul(main, main_rate)
        remaining -= main

    if remaining > 0:
        contribution += fp.mul(remaining, additional_rate)

    return contribution


def employer_national_insurance(
    salary: int,
    *,
    secondary_threshold: int,
    rate: int,
) -> int:
    """
    Compute employer National Insurance.

    Args:
        salary: The gross salary at `SCALE`.
        secondary_threshold: The threshold where employer contributions
            start, at `SCALE`.
        rate: The employer rate at `SCALE`.

    Returns:
        The employer contribution at `SCALE`.
    """
    if salary <= 0:
        return 0
    return fp.mul(max(salary - secondary_threshold, 0), rate)


def corporation_tax(
    profit: int,
    *,
    small_profits_rate: int,
    main_rate: int,
    lower_limit: int,
    upper_limit: int,
    marginal_relief_fraction: int,
) -> int:
    """
    Compute corporation tax with marginal relief.

    Args:
        profit: The taxable profit at `SCALE`.
        small_profits_rate: The small profits rate at `SCALE`.
        main_rate: The main rate at `SCALE`.
        lower_limit: The lower profit limit at `SCALE`.
        upper_limit: The upper profit limit at `SCALE`.
        marginal_relief_fraction: The marginal relief fraction at `SCALE`.

    Returns:
        The corporation tax at `SCALE`.
    """
    if profit <= 0:
        return 0
    if profit <= lower_limit:
        return fp.mul(profit, small_profits_rate)
    if profit >= upper_limit:
        return fp.mul(profit, main_rate)
    relief = fp.mul(upper_limit - profit, marginal_relief_fraction)
    return fp.mul(profit, main_rate) - relief


def pension_contribution(gross: int, rate: int) -> int:
    """
    Compute a pension contribution.

    Args:
        gross: The gross amount at `SCALE`.
        rate: The contribution rate at `SCALE`.

    Returns:
        The contribution at `SCALE`.
    """
    if gross <= 0:
        return 0
    return fp.mul(gross, rate)


def student_loan_repayment(gross: int, *, threshold: int, rate: int) -> int:
    """
    Compute a student loan repayment.

    Args:
        gross: The gross amount at `SCALE`.
        threshold: The income threshold at `SCALE`.
        rate: The repayment rate at `SCALE`.

    Returns:
        The repayment at `SCALE`.
    """
    if gross <= 0:
        return 0
    if gross <= threshold:
        return 0
    return fp.mul(gross - threshold, rate)


def dividend_tax(
    dividends: int,
    *,
    other_income: int,
    personal_allowance: int,
    standard_personal_allowance: int | None = None,
    basic_rate_limit: int,
    higher_rate_limit: int,
    allowance: int,
    basic_rate: int,
    higher_rate: int,
    additional_rate: int,
) -> int:
    """
    Compute dividend tax after other income and the dividend allowance.

    Args:
        dividends: The dividend amount at `SCALE`.
        other_income: Income taxed before dividends, at `SCALE`.
        personal_allowance: The tax-free allowance at `SCALE`.
        standard_personal_allowance: The standard allowance before any taper,
            at `SCALE`. Defaults to `personal_allowance`.
        basic_rate_limit: The upper limit of the basic band at `SCALE`.
        higher_rate_limit: The upper limit of the higher band at `SCALE`.
        allowance: The dividend allowance at `SCALE`.
        basic_rate: The dividend basic rate at `SCALE`.
        higher_rate: The dividend higher rate at `SCALE`.
        additional_rate: The dividend additional rate at `SCALE`.

    Returns:
        The dividend tax at `SCALE`.
    """
    if dividends <= 0:
        return 0

    standard = (
        personal_allowance
        if standard_personal_allowance is None
        else standard_personal_allowance
    )
    allowance_used_by_other = min(personal_allowance, max(other_income, 0))
    allowance_left = personal_allowance - allowance_used_by_other
    taxable_dividends = max(dividends - allowance_left, 0)
    if taxable_dividends <= 0:
        return 0

    allowance_slice = min(taxable_dividends, allowance)
    remaining = taxable_dividends - allowance_slice
    if remaining <= 0:
        return 0

    taxable_other = max(other_income - personal_allowance, 0)
    basic_band_end = max(basic_rate_limit - standard, 0)
    higher_band_end = max(higher_rate_limit - standard, 0)
    position = taxable_other + allowance_slice

    basic_room = max(basic_band_end - position, 0)
    basic_slice = min(remaining, basic_room)
    remaining -= basic_slice
    position += basic_slice

    higher_room = max(higher_band_end - position, 0)
    higher_slice = min(remaining, higher_room)
    remaining -= higher_slice

    return (
        fp.mul(basic_slice, basic_rate)
        + fp.mul(higher_slice, higher_rate)
        + fp.mul(remaining, additional_rate)
    )


def capital_gains_tax(
    gains: int,
    *,
    other_income: int,
    personal_allowance: int,
    standard_personal_allowance: int | None = None,
    annual_exempt_amount: int,
    basic_rate_limit: int,
    basic_rate: int,
    higher_rate: int,
) -> int:
    """
    Compute capital gains tax on a realised gain.

    The gain fills the basic rate band that remains after other taxable
    income. Any gain above that band is taxed at the higher rate.

    Args:
        gains: The realised gain at `SCALE`.
        other_income: Income taxed before the gain, at `SCALE`.
        personal_allowance: The income tax personal allowance at `SCALE`.
        standard_personal_allowance: The standard allowance before any taper,
            at `SCALE`. Defaults to `personal_allowance`.
        annual_exempt_amount: The capital gains tax-free allowance at `SCALE`.
        basic_rate_limit: The upper limit of the basic income tax band at
            `SCALE`.
        basic_rate: The capital gains basic rate at `SCALE`.
        higher_rate: The capital gains higher rate at `SCALE`.

    Returns:
        The capital gains tax at `SCALE`.
    """
    if gains <= 0:
        return 0

    taxable_gain = max(gains - annual_exempt_amount, 0)
    if taxable_gain <= 0:
        return 0

    standard = (
        personal_allowance
        if standard_personal_allowance is None
        else standard_personal_allowance
    )
    taxable_income = max(other_income - personal_allowance, 0)
    basic_band_end = max(basic_rate_limit - standard, 0)
    basic_room = max(basic_band_end - taxable_income, 0)
    basic_gain = min(taxable_gain, basic_room)
    higher_gain = taxable_gain - basic_gain

    return fp.mul(basic_gain, basic_rate) + fp.mul(higher_gain, higher_rate)


def isa_tax(isa_income: int, *, rate: int = 0) -> int:
    """
    Compute tax on ISA income.

    Args:
        isa_income: The income at `SCALE`.
        rate: The ISA tax rate at `SCALE`. The default is zero because ISAs
            are tax-free.

    Returns:
        The tax at `SCALE`.
    """
    if isa_income <= 0:
        return 0
    return fp.mul(isa_income, rate)
