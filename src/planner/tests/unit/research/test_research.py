from planner.research.allowlist import is_allowed_url
from planner.research.html import (
    decode_result_url,
    extract_text,
    extract_title,
    parse_search_results,
)


def test_allowed_sources():
    assert is_allowed_url("https://www.gov.uk/income-tax-rates")
    assert is_allowed_url("https://www.legislation.gov.uk/ukpga/2026/1")
    assert is_allowed_url("https://www.fca.org.uk/consumers")
    assert is_allowed_url("https://www.cbn.gov.ng")
    assert is_allowed_url("https://www.nrs.gov.ng/")
    assert is_allowed_url("https://www.pwc.com/gx/en.html")
    assert is_allowed_url("https://taxsummaries.pwc.com")
    assert is_allowed_url("https://taxsummaries.pwc.com/united-kingdom")


def test_non_allowed_urls_are_rejected():
    assert not is_allowed_url("https://example.com/tax")
    assert not is_allowed_url("http://www.gov.uk/income-tax-rates")
    assert not is_allowed_url("https://gov.uk.evil.com/tax")
    assert not is_allowed_url("https://www.gov.ng")


def test_duckduckgo_redirect_is_decoded():
    href = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.gov.uk%2Fincome-tax-rates&rut=abc"
    )
    assert decode_result_url(href) == "https://www.gov.uk/income-tax-rates"


def test_search_results_are_parsed():
    html = """
    <div class="result">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.gov.uk%2Ftax">
        Income Tax rates
      </a>
      <a class="result__snippet">Rates and allowances for the current year.</a>
    </div>
    """
    hits = parse_search_results(html, 5)
    assert len(hits) == 1
    assert hits[0].title == "Income Tax rates"
    assert hits[0].url == "https://www.gov.uk/tax"
    assert hits[0].snippet == "Rates and allowances for the current year."


def test_page_text_skips_scripts_and_styles():
    html = """
    <html>
      <head><title>Tax page</title><style>.x { color: red; }</style></head>
      <body>
        <script>alert('no')</script>
        <p>First paragraph.</p>
        <p>Second paragraph.</p>
      </body>
    </html>
    """
    assert extract_title(html) == "Tax page"
    assert extract_text(html) == "First paragraph. Second paragraph."
