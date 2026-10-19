from planner.agent.adapters.langchain import _text_from_content


def test_extracts_only_text_blocks():
    content = [
        {"type": "thinking", "thinking": "", "signature": "abc"},
        {"type": "text", "text": "Your net pay is £34,622.40."},
    ]
    assert _text_from_content(content) == "Your net pay is £34,622.40."


def test_plain_string_content_is_returned():
    assert _text_from_content("hello") == "hello"


def test_empty_content_returns_empty_string():
    assert _text_from_content([]) == ""
