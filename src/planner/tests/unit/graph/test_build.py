from planner.graph.build import MAX_NARRATION_ATTEMPTS, build


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


def test_narration_retry_limit_is_explicit():
    assert MAX_NARRATION_ATTEMPTS == 3
