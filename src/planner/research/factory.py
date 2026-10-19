import os
from functools import cache

from planner.research.adapters.fake import FakeResearch
from planner.research.adapters.http import HttpResearch
from planner.research.ports import ResearchPort


@cache
def research() -> ResearchPort:
    if os.environ.get("PLANNER_FAKE_RESEARCH"):
        return FakeResearch()
    return HttpResearch(timeout=float(os.environ.get("PLANNER_RESEARCH_TIMEOUT", "10")))
