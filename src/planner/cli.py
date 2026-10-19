import argparse
import asyncio
import os
import re
from collections.abc import Awaitable
from datetime import date
from typing import Any, cast

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from planner.graph.runtime import compiled, config
from planner.graph.state import PlanState, Profile
from planner.telemetry import configure_tracing

MAX_QUESTIONS = 5

QUESTIONS = {
    "country": "Country (ISO code, for example GB or NG)",
    "gross_annual": "Gross annual salary or income (for example 45,000)",
    "scottish_taxpayer": "Scottish taxpayer (yes or no)",
    "pension_rate": "Pension contribution rate (for example 6% or 0.06)",
    "company_profit": "Company profit before director pay (for example 100,000)",
    "director_salary": "Director salary paid by the company (for example 12,570)",
    "distributable_reserves": (
        "Retained profit available for dividends (for example 0)"
    ),
    "existing_paye_income": "Existing PAYE salary or income (for example 85,000)",
    "pension_income": "Pension income (for example 10,000)",
    "rental_income": "Rental income (for example 12,000)",
    "other_income": "Other taxable income (for example 5,000)",
    "student_loan_plan": "Student loan plan (plan1, plan2, plan4, plan5 or postgraduate)",
    "savings_amount": "Amount to invest (for example 10,000)",
    "annual_growth_rate": "Expected annual growth rate (for example 5% or 0.05)",
    "investment_years": "Number of years invested (for example 10)",
}

# The report carries [r:<result_id>.<key>] markers. The validator needs them;
# the person reading the CLI does not.
_MARKER = re.compile(r"\s*\[r:[0-9a-f]{12}\.[a-z_]+\]")


def _db_url() -> str:
    url = os.environ.get("PLANNER_DB_URL")
    if not url:
        raise RuntimeError("PLANNER_DB_URL is not set")
    return url


async def run(thread_id: str, message: str, planning_date: date) -> dict[str, Any]:
    async with compiled(_db_url()) as graph:
        snapshot = await graph.aget_state(config(thread_id))
        existing = snapshot.values.get("profile")
        profile = (
            existing.model_copy(update={"planning_date": planning_date})
            if isinstance(existing, Profile)
            else Profile(planning_date=planning_date)
        )
        return cast(
            dict[str, Any],
            await graph.ainvoke(
                PlanState(
                    messages=[HumanMessage(content=message)],
                    profile=profile,
                ),
                config(thread_id),
                durability="sync",
            ),
        )


async def resume(thread_id: str, answer: str | None) -> dict[str, Any]:
    """
    Continue a run that is paused or crashed.

    Args:
        thread_id: The thread to continue.
        answer: The reply to a pending interrupt, or None to continue a
            crashed run.

    Returns:
        The run state after the graph advances.
    """
    async with compiled(_db_url()) as graph:
        return cast(
            dict[str, Any],
            await graph.ainvoke(
                None if answer is None else Command(resume=answer),
                config(thread_id),
                durability="sync",
            ),
        )


async def history(thread_id: str) -> list[tuple[str, tuple[str, ...]]]:
    async with compiled(_db_url()) as graph:
        out: list[tuple[str, tuple[str, ...]]] = []
        async for snap in graph.aget_state_history(config(thread_id)):
            checkpoint_id = snap.config.get("configurable", {}).get("checkpoint_id", "")
            out.append((checkpoint_id, snap.next))
        return out


def _interrupt_value(out: dict[str, Any]) -> dict[str, Any]:
    interrupts = out.get("__interrupt__") or []
    if not interrupts:
        return {}
    value = interrupts[0].value
    return value if isinstance(value, dict) else {}


def _missing_fields(out: dict[str, Any]) -> list[str]:
    value = _interrupt_value(out)
    return [str(field) for field in value.get("fields", [])]


def _ask(fields: list[str]) -> str:
    answers: list[str] = []
    for field in fields:
        question = QUESTIONS.get(field, field.replace("_", " "))
        try:
            value = input(f"{question}: ").strip()
        except EOFError:
            return ""
        answers.append(f"{field}: {value}")
    return "\n".join(answers)


def _ask_free_text(message: str) -> str:
    try:
        return input(f"{message} ").strip()
    except EOFError:
        return ""


async def _converse(thread_id: str, first: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    out = await first
    asked = 0
    while True:
        value = _interrupt_value(out)
        fields = [str(field) for field in value.get("fields", [])]
        message = str(value.get("message", ""))
        if not fields and not message:
            break
        if asked >= MAX_QUESTIONS:
            break
        asked += 1
        if fields:
            if message:
                print(message)
            answer = _ask(fields)
        else:
            answer = _ask_free_text(message)
        if not answer:
            break
        out = await resume(thread_id, answer)
    return out


def _print_result(out: dict[str, Any]) -> None:
    if fields := _missing_fields(out):
        print("Still missing: " + ", ".join(fields))
        return
    if failure := out.get("failure"):
        print(f"No figures: {failure}")
        return
    report = out.get("report")
    if report is None:
        print("No report was produced.")
        return
    print(_MARKER.sub("", report.text))
    if report.citations:
        print("\nFigures:")
        for citation in report.citations:
            label = citation.key.replace("_", " ")
            print(f"  {citation.shown}  ({label})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="planner")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("thread_id")
    run_parser.add_argument("message")
    run_parser.add_argument("--date", required=True, type=date.fromisoformat)

    resume_parser = sub.add_parser("resume")
    resume_parser.add_argument("thread_id")
    resume_parser.add_argument("answer", nargs="?")

    history_parser = sub.add_parser("history")
    history_parser.add_argument("thread_id")

    args = parser.parse_args(argv)
    configure_tracing()
    if args.command == "run":
        out = asyncio.run(
            _converse(args.thread_id, run(args.thread_id, args.message, args.date))
        )
    elif args.command == "resume":
        out = asyncio.run(
            _converse(args.thread_id, resume(args.thread_id, args.answer))
        )
    else:
        for checkpoint_id, next_nodes in asyncio.run(history(args.thread_id)):
            print(f"{checkpoint_id} next={','.join(next_nodes) or 'END'}")
        return
    _print_result(out)


if __name__ == "__main__":
    main()
