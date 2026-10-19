import ast
from pathlib import Path

import planner

CALCULATORS = Path(planner.__file__).parent / "jurisdictions"


def _calculator_files() -> list[Path]:
    return sorted(CALCULATORS.rglob("calculators/*.py"))


def test_calculator_files_exist():
    assert _calculator_files(), "expected at least one calculator module"


def test_no_float_in_calculators():
    offenders: list[str] = []
    for path in _calculator_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                offenders.append(f"{path}:{node.lineno}: float literal {node.value!r}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"float", "Decimal"}
            ):
                offenders.append(f"{path}:{node.lineno}: {node.func.id}()")
    assert not offenders, "\n".join(offenders)
