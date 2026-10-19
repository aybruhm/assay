from datetime import UTC, datetime
from typing import Any

import pytest

from planner.audit.events import AuditEvent, Kind
from planner.audit.sink import AuditError, InMemorySink, ProvenanceSink, sink


def _event(kind: Kind = "calculation") -> AuditEvent:
    return AuditEvent(
        kind=kind,
        thread_id="t-1",
        at=datetime.now(UTC),
        data={"result_id": "9f2c1a3b4d5e"},
    )


class TestInMemorySink:
    def test_records_batches(self):
        audit_sink = InMemorySink()
        events = [_event()]
        audit_sink.record_batch(events, "t-1:delivery")
        assert audit_sink.batches == [(events, "t-1:delivery")]

    def test_injected_failure_raises(self):
        audit_sink = InMemorySink(fail=True)
        with pytest.raises(AuditError):
            audit_sink.record_batch([_event()], "t-1:delivery")


class FakeGateway:
    """Records execute calls; can be told to fail like a dead gateway."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[
            tuple[str, dict[str, str | int | bool | list[str]], str | None, Any]
        ] = []

    def execute(
        self,
        action: str,
        parameters: dict[str, str | int | bool | list[str]],
        *,
        session_id: str | None = None,
        decision: object | None = None,
    ) -> object:
        if self.error is not None:
            raise self.error
        self.calls.append((action, parameters, session_id, decision))
        return object()


class TestProvenanceSink:
    def test_each_event_is_one_gateway_execute(self):
        gateway = FakeGateway()
        audit_sink = ProvenanceSink(gateway)
        audit_sink.record_batch(
            [_event("calculation"), _event("delivery")], "t-1:delivery"
        )
        assert [call[0] for call in gateway.calls] == [
            "planner.calculation",
            "planner.delivery",
        ]
        assert all(call[2] == "t-1:delivery" for call in gateway.calls)
        assert all(str(call[3]) == "Decision.ALLOW" for call in gateway.calls)
        parameters = gateway.calls[0][1]
        assert parameters["result_id"] == "9f2c1a3b4d5e"
        assert "at" in parameters and "thread_id" in parameters

    def test_gateway_outage_becomes_audit_error(self):
        from provenance_client.services import GatewayError

        gateway = FakeGateway(
            error=GatewayError("http://gateway", ConnectionError("down"))
        )
        audit_sink = ProvenanceSink(gateway)
        with pytest.raises(AuditError):
            audit_sink.record_batch([_event()], "t-1:delivery")

    def test_blocked_decision_becomes_audit_error(self):
        from provenance_client.services import PolicyBlockedError

        gateway = FakeGateway(
            error=PolicyBlockedError("planner.calculation", "denied", "evt-1")
        )
        audit_sink = ProvenanceSink(gateway)
        with pytest.raises(AuditError):
            audit_sink.record_batch([_event()], "t-1:delivery")


def test_factory_requires_configuration(monkeypatch):
    monkeypatch.delenv("PLANNER_FAKE_SINK", raising=False)
    monkeypatch.delenv("PROVENANCE_GATEWAY_URL", raising=False)
    sink.cache_clear()
    with pytest.raises(RuntimeError, match="PROVENANCE_GATEWAY_URL"):
        sink()


def test_factory_selects_in_memory_sink(monkeypatch):
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")
    sink.cache_clear()
    assert isinstance(sink(), InMemorySink)
