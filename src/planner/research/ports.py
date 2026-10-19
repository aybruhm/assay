from typing import Protocol

from planner.research.models import FetchedPage, SearchHit


class ResearchError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ResearchPort(Protocol):
    """Read-only access to trusted web sources."""

    def search(self, query: str, max_results: int) -> list[SearchHit]: ...

    def fetch(self, url: str) -> FetchedPage: ...
