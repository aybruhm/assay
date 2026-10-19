from pathlib import Path

from planner.graph.build import MAX_NARRATION_ATTEMPTS, build

DOCS = Path(__file__).resolve().parents[5] / "docs" / "graph.mmd"


def test_graph_compiles():
    graph = build().compile()
    nodes = set(graph.get_graph().nodes)
    assert {
        "intake",
        "ask_user",
        "prepare",
        "agent",
        "execute_tools",
        "narrate",
        "validate",
        "deliver",
        "fail_closed",
    } <= nodes


def test_mermaid_snapshot_unchanged():
    """
    Fail when the graph wiring no longer matches the committed diagram.
    """
    current = build().compile().get_graph().draw_mermaid()
    assert current == DOCS.read_text()


def test_narration_retry_limit_is_explicit():
    assert MAX_NARRATION_ATTEMPTS == 3
