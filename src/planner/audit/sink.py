import asyncio
import os
from functools import cache
from typing import Protocol

from provenance_client import Decision, ProvenanceClient, ProvenanceGateway
from provenance_client.services import GatewayError, PolicyBlockedError

from planner.audit.events import AuditEvent


class AuditError(Exception):
    pass


class AuditSink(Protocol):
    """Driven port: send one run's events as a batch keyed by idempotency key."""

    async def record_batch(
        self, events: list[AuditEvent], idempotency_key: str
    ) -> None: ...


class Gateway(Protocol):
    """The slice of the Provenance gateway the sink uses.

    Kept as a protocol (not the SDK's concrete class) so the adapter can be
    tested with a fake gateway that is not a ProvenanceGateway subclass.
    """

    def execute(
        self,
        action: str,
        parameters: dict[str, str | int | bool | list[str]],
        *,
        session_id: str | None = None,
        decision: Decision | None = None,
    ) -> object: ...


class ProvenanceSink:
    """Adapter over provenance-client's policy gateway."""

    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway

    async def record_batch(
        self, events: list[AuditEvent], idempotency_key: str
    ) -> None:
        try:
            await asyncio.gather(
                *(
                    asyncio.to_thread(
                        self._gateway.execute,
                        f"planner.{event.kind}",
                        {
                            "thread_id": event.thread_id,
                            "at": event.at.isoformat(),
                            **event.data,
                        },
                        session_id=idempotency_key,
                        decision=Decision.ALLOW,
                    )
                    for event in events
                )
            )
        except (GatewayError, PolicyBlockedError) as exc:
            raise AuditError(str(exc)) from exc


class InMemorySink:
    """Test double: records batches for assertions; fails on demand."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.batches: list[tuple[list[AuditEvent], str]] = []

    async def record_batch(
        self, events: list[AuditEvent], idempotency_key: str
    ) -> None:
        if self.fail:
            raise AuditError("injected failure")
        self.batches.append((events, idempotency_key))


@cache
def sink() -> AuditSink:
    """
    Return the configured audit sink.

    Returns:
        The in-memory sink when `PLANNER_FAKE_SINK` is set, otherwise a sink
        over the Provenance gateway.

    Raises:
        RuntimeError: If `PROVENANCE_GATEWAY_URL` is not set.
    """
    if os.environ.get("PLANNER_FAKE_SINK"):
        return InMemorySink()

    gateway_url = os.environ.get("PROVENANCE_GATEWAY_URL")
    if not gateway_url:
        raise RuntimeError(
            "PROVENANCE_GATEWAY_URL is not set. Point it at the Provenance "
            "gateway or set PLANNER_FAKE_SINK=1 to use the in-memory sink."
        )
    gateway = ProvenanceGateway(
        ProvenanceClient(
            gateway_url=gateway_url,
            agent_id=os.environ.get("PROVENANCE_AGENT_ID", "planner"),
            api_key=os.environ.get("PROVENANCE_API_KEY"),
            # Audit failure must fail closed: a dead gateway blocks delivery.
            on_gateway_error="closed",
        )
    )
    return ProvenanceSink(gateway)
