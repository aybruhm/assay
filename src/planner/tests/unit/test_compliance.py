import pytest

from planner.compliance import recommendation_violations


@pytest.mark.parametrize(
    "text",
    [
        "You should take the full dividend.",
        "You ought to take the full dividend.",
        "I recommend the full dividend.",
        "My recommendation is the full dividend.",
        "The full dividend is the best option.",
        "Option A is better than option B.",
        "Choose the full dividend.",
        "Pick the full dividend.",
        "Take the full amount.",
        "Pay yourself the full amount.",
        "Invest the £10,000.00 in the ISA.",
        "Consider the full dividend.",
        "If I were you, I would take the full dividend.",
        "I’d take the full dividend.",
        "The right choice is the full dividend.",
        "The options are ranked below.",
        "The full dividend is the most tax-efficient option.",
        "The full dividend is the preferred option.",
        "This is not advice. You should take the full dividend.",
        "This is not a recommendation, but the full dividend is optimal.",
        "Most people in your position take the full dividend.",
        "It may be worth taking the full dividend.",
    ],
)
def test_recommendation_language_is_rejected(text):
    assert recommendation_violations(text)


@pytest.mark.parametrize(
    "text",
    [
        "Option A leaves £57,487.50 in the company. Option B leaves £0.",
        "Option B pays £30,290.69 more now.",
        "If your goal is to leave money in the company, option A leaves more.",
        "The higher rate applies above £50,270.00.",
        "The basic rate is 20%.",
        "This is not a recommendation.",
        "This is not financial advice.",
        "This is not tax advice.",
        "The figures are not advice.",
        "The figures do not include your preferences.",
        "The company can pay a dividend in a later tax year.",
        "Most people pay income tax through PAYE.",
    ],
)
def test_neutral_figures_and_comparisons_pass(text):
    assert recommendation_violations(text) == []


def test_urls_and_markers_are_ignored():
    text = (
        "Read https://example.com/best-practice for the rule. "
        "Net pay is £34,622.40 [r:9f2c1a3b4d5e.net_pay]."
    )
    assert recommendation_violations(text) == []


def test_duplicate_phrases_are_reported_once():
    messages = recommendation_violations(
        "You should take the full dividend. You should check the figures."
    )
    assert len(messages) == 1
    assert "'You should'" in messages[0]


def test_disclaimer_does_not_hide_advice():
    messages = recommendation_violations(
        "This is not advice. You should take the full dividend."
    )
    assert any("You should" in message for message in messages)
