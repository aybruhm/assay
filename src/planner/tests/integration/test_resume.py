import os
import subprocess
import sys
from uuid import uuid4

import pytest

from planner.graph.runtime import compiled, config
from planner.jurisdictions.gb import GB


async def test_resume_after_crash_does_not_recompute(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_id = str(uuid4())
    env = {
        **os.environ,
        "PLANNER_CRASH_AT": "narrate",
        "PLANNER_FAKE_MODEL": "1",
        "PLANNER_FAKE_SINK": "1",
        "PLANNER_DB_URL": db_url,
    }
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "planner.cli",
            "run",
            thread_id,
            "I earn 45,000 a year in England",
            "--date",
            "2026-10-01",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 137, process.stderr  # killed as narrate started

    calls: list[int] = []
    input_model, real_calculator = GB.calculators["gb.take_home"]

    def counting(calculator_input, pack):
        calls.append(1)
        return real_calculator(calculator_input, pack)

    monkeypatch.setitem(GB.calculators, "gb.take_home", (input_model, counting))
    monkeypatch.setenv("PLANNER_FAKE_MODEL", "1")
    monkeypatch.setenv("PLANNER_FAKE_SINK", "1")

    async with compiled(db_url) as graph:
        before = (await graph.aget_state(config(thread_id))).values["results"]
        out = await graph.ainvoke(None, config(thread_id))

    assert calls == []  # calculator did not run again
    assert [result.result_id for result in out["results"]] == [
        result.result_id for result in before
    ]
    assert out["validation"].status == "passed"
