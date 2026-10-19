from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str = ""


class FetchedPage(BaseModel):
    title: str
    url: str
    text: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchResult(BaseModel):
    research_id: str
    kind: Literal["search", "page"]
    title: str
    url: str
    snippet: str = ""
    text: str | None = None
    query: str | None = None
    fetched_at: datetime
