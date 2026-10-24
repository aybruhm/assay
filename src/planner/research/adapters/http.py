import os
from urllib.parse import quote_plus

import httpx

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

    async def _get(self, url: str, *, require_allowed: bool) -> tuple[str, str]:
        if require_allowed and not is_allowed_url(url):
            raise ResearchError(f"not a trusted source: {url}")
        try:
            async with (
                httpx.AsyncClient(
                    timeout=self._timeout,
                    headers={"User-Agent": self._user_agent},
                    follow_redirects=True,
                ) as client,
                client.stream("GET", url) as response,
            ):
                final_url = str(response.url)
                if require_allowed and not is_allowed_url(final_url):
                    raise ResearchError(
                        f"redirected to a non-trusted source: {final_url}"
                    )
                response.raise_for_status()
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) >= _MAX_BYTES:
                        break
                charset = response.encoding or "utf-8"
        except httpx.HTTPStatusError as exc:
            raise ResearchError(f"HTTP {exc.response.status_code} for {url}") from exc
        except (httpx.RequestError, TimeoutError) as exc:
            raise ResearchError(f"could not reach {url}: {exc}") from exc
        return final_url, bytes(payload[:_MAX_BYTES]).decode(charset, errors="replace")

    async def search(self, query: str, max_results: int) -> list[SearchHit]:
        url = _SEARCH_URL.format(query=quote_plus(query))
        _, html_text = await self._get(url, require_allowed=False)
        hits = parse_search_results(html_text, max_results)
        return [hit for hit in hits if is_allowed_url(hit.url)]

    async def fetch(self, url: str) -> FetchedPage:
        final_url, html_text = await self._get(url, require_allowed=True)
        return FetchedPage(
            title=extract_title(html_text) or final_url,
            url=final_url,
            text=extract_text(html_text),
        )
