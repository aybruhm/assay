import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from planner.research.allowlist import is_allowed_url
from planner.research.html import (
    extract_text,
    extract_title,
    parse_search_results,
)
from planner.research.models import FetchedPage, SearchHit
from planner.research.ports import ResearchError

_SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
_MAX_BYTES = 512_000


class HttpResearch:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._user_agent = os.environ.get(
            "PLANNER_RESEARCH_USER_AGENT",
            "Assay/0.1 (trusted source research)",
        )

    def _get(self, url: str, *, require_allowed: bool) -> tuple[str, str]:
        if require_allowed and not is_allowed_url(url):
            raise ResearchError(f"not a trusted source: {url}")
        request = Request(url, headers={"User-Agent": self._user_agent})
        try:
            with urlopen(request, timeout=self._timeout) as response:
                final_url = response.geturl()
                if require_allowed and not is_allowed_url(final_url):
                    raise ResearchError(
                        f"redirected to a non-trusted source: {final_url}"
                    )
                payload = response.read(_MAX_BYTES)
                charset = response.headers.get_content_charset() or "utf-8"
        except HTTPError as exc:
            raise ResearchError(f"HTTP {exc.code} for {url}") from exc
        except (URLError, TimeoutError) as exc:
            raise ResearchError(f"could not reach {url}: {exc}") from exc
        return final_url, payload.decode(charset, errors="replace")

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        url = _SEARCH_URL.format(query=quote_plus(query))
        _, html_text = self._get(url, require_allowed=False)
        hits = parse_search_results(html_text, max_results)
        return [hit for hit in hits if is_allowed_url(hit.url)]

    def fetch(self, url: str) -> FetchedPage:
        final_url, html_text = self._get(url, require_allowed=True)
        return FetchedPage(
            title=extract_title(html_text) or final_url,
            url=final_url,
            text=extract_text(html_text),
        )
