from planner.research.models import FetchedPage, SearchHit
from planner.research.ports import ResearchError


class FakeResearch:
    def __init__(
        self,
        hits: list[SearchHit] | None = None,
        pages: dict[str, FetchedPage] | None = None,
        fail: bool = False,
    ) -> None:
        self._hits = list(hits or [])
        self._pages = dict(pages or {})
        self._fail = fail
        self.queries: list[tuple[str, int]] = []
        self.fetches: list[str] = []

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        self.queries.append((query, max_results))
        if self._fail:
            raise ResearchError("injected search failure")
        return self._hits[:max_results]

    def fetch(self, url: str) -> FetchedPage:
        self.fetches.append(url)
        if self._fail:
            raise ResearchError("injected fetch failure")
        page = self._pages.get(url)
        if page is None:
            raise ResearchError(f"page not found: {url}")
        return page
