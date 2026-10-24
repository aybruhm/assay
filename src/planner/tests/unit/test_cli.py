from planner.cli import _figures_table
from planner.graph.state import Citation


def test_figures_are_printed_as_an_aligned_table():
    table = _figures_table(
        [
            Citation(result_id="9f2c1a3b4d5e", key="existing_paye_income", shown="\u00a385,000.00"),
            Citation(result_id="9f2c1a3b4d5e", key="dividend_tax", shown="\u00a35,183.75"),
        ]
    )
    assert table.splitlines() == [
        "Figure                    Amount",
        "--------------------  ----------",
        "Existing paye income  \u00a385,000.00",
        "Dividend tax           \u00a35,183.75",
    ]
