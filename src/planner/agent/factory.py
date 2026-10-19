import os
from functools import cache

from planner.agent.adapters.fake import ScriptedModel
from planner.agent.adapters.langchain import LangChainModel
from planner.agent.ports import ModelPort


@cache
def model() -> ModelPort:
    """
    Return the configured model adapter.

    Returns:
        The scripted adapter when `PLANNER_FAKE_MODEL` is set, otherwise a
        LangChain adapter for `PLANNER_MODEL`.

    Raises:
        RuntimeError: If `PLANNER_MODEL` is not set and `PLANNER_FAKE_MODEL`
            is not enabled.
    """

    if os.environ.get("PLANNER_FAKE_MODEL"):
        return ScriptedModel()

    model_name = os.environ.get("PLANNER_MODEL")
    if not model_name:
        raise RuntimeError(
            "PLANNER_MODEL is not set. Set it to a LangChain model name "
            "(e.g. PLANNER_MODEL=anthropic:claude-sonnet-4) or set "
            "PLANNER_FAKE_MODEL=1 to use the in-memory fake adapter."
        )
    return LangChainModel(model_name)
