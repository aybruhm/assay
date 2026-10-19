import json

from langchain_core.messages import AnyMessage

from planner.agent.models import AgentDecision, ProfileExtraction, ToolCall
from planner.agent.ports import ModelPort


class ScriptedModel(ModelPort):
    """In-memory fake adapter for tests and local development.

    With no scripts it behaves as the demo fake: a complete GB profile
    (country, gross annual salary, non-Scottish), a take-home tool call, and
    a narration composed from the markers it is given.
    """

    def __init__(
        self,
        extractions: list[ProfileExtraction] | None = None,
        decisions: list[AgentDecision] | None = None,
        narrations: list[str] | None = None,
    ) -> None:
        self._extractions = list(extractions or [])
        self._decisions = list(decisions or [])
        self._narrations = list(narrations or [])

    def extract_profile(self, messages: list[AnyMessage]) -> ProfileExtraction:
        if self._extractions:
            return self._extractions.pop(0)
        return ProfileExtraction(
            country="GB",
            pension_income=None,
            company_profit=None,
            director_salary=None,
            savings_amount=None,
            annual_growth_rate=None,
            investment_years=None,
            pension_rate=None,
            distributable_reserves=None,
            gross_annual="45,000.00",
            scottish_taxpayer=False,
            other_income=None,
            student_loan_plan=None,
            rental_income=None,
        )

    def decide(self, system: str, payload: str) -> AgentDecision:
        if self._decisions:
            return self._decisions.pop(0)
        try:
            data = json.loads(payload)
        except ValueError, TypeError:
            return AgentDecision(action="respond")
        profile = data.get("PROFILE", {})
        results = data.get("TOOL_RESULTS", [])
        errors = data.get("TOOL_ERRORS", [])
        if results or errors:
            return AgentDecision(action="respond")
        if not profile.get("country"):
            return AgentDecision(
                action="ask",
                fields=["country"],
                message="Which country are you in?",
            )
        if profile.get("gross_annual"):
            return AgentDecision(
                action="call_tools",
                tool_calls=[ToolCall(name="take_home", arguments={})],
            )
        return AgentDecision(
            action="ask",
            fields=["gross_annual"],
            message="What is your gross annual income?",
        )

    def narrate(self, system: str, payload: str) -> str:
        if self._narrations:
            return self._narrations.pop(0)
        try:
            facts = json.loads(payload)["RESULTS"]
        except ValueError, KeyError, TypeError:
            return payload
        sentences = [
            f"Your {fact['label'].replace('_', ' ')} is "
            f"{fact['figure']} {fact['marker']}."
            for fact in facts
        ]
        return " ".join(sentences)
