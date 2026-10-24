from typing import Protocol

from langchain_core.messages import AnyMessage

from planner.agent.models import AgentDecision, ProfileExtraction


class ModelPort(Protocol):
    """Driven port for language-model capabilities.

    Domain code depends only on this protocol. Concrete implementations live
    in ``planner.agent.adapters`` and are wired up by ``planner.agent.factory``.
    """

    async def extract_profile(
        self, messages: list[AnyMessage]
    ) -> ProfileExtraction: ...

    async def decide(self, system: str, payload: str) -> AgentDecision: ...

    async def narrate(self, system: str, payload: str) -> str: ...
