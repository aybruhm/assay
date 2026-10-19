from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph.state import CompiledStateGraph

from planner.agent.models import AgentDecision, ToolCall
from planner.core.types import CalcLine, CalcResult
from planner.graph.build import build
from planner.graph.state import (
    Approval,
    Citation,
    PlanState,
    Profile,
    Report,
    ToolRecord,
    Validation,
)
from planner.research.models import ResearchResult
from planner.rules.schema import RulePackRef

# The types the checkpointer serializes into checkpoint state. Registering
# them keeps deserialization working once strict msgpack mode becomes the
# default in a future langgraph release.
_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        PlanState,
        CalcResult,
        CalcLine,
        Profile,
        Citation,
        Report,
        Validation,
        Approval,
        ToolCall,
        ToolRecord,
        ResearchResult,
        AgentDecision,
        RulePackRef,
    ]
)


@asynccontextmanager
async def compiled(
    db_url: str,
) -> AsyncGenerator[CompiledStateGraph[PlanState, None, PlanState, PlanState]]:
    async with AsyncPostgresSaver.from_conn_string(db_url, serde=_SERDE) as saver:
        await saver.setup()  # idempotent: creates checkpoint tables if missing
        yield build().compile(checkpointer=saver)


def config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}
