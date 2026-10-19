from urllib.parse import urlparse

ALLOWED_HOST_SUFFIXES = (
    "gov.uk",
    "legislation.gov.uk",
    "fca.org.uk",
    "ico.org.uk",
    "ons.gov.uk",
    "bankofengland.co.uk",
    "gov.scot",
    "gov.wales",
    "nidirect.gov.uk",
    "cbn.gov.ng",
    "nrs.gov.ng",
    "pwc.com",
    "taxsummaries.pwc.com",
)


def is_allowed_url(url: str) -> bool:
    """
    Return whether a URL is an allowlisted trusted source.

    Args:
        url: The URL to check.

    Returns:
        True when the URL uses HTTPS and its host is on the allowlist.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in ALLOWED_HOST_SUFFIXES
    )
