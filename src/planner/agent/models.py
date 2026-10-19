from typing import Literal

from pydantic import BaseModel, Field


class ProfileExtraction(BaseModel):
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 code")
    gross_annual: str | None = Field(
        None,
        description=(
            "Gross annual salary or income exactly as the user wrote it, "
            "for example '45,000' or '45000.50'."
        ),
    )
    pension_income: str | None = Field(
        None, description="Pension income exactly as the user wrote it."
    )
    rental_income: str | None = Field(
        None, description="Rental income exactly as the user wrote it."
    )
    other_income: str | None = Field(
        None,
        description="Other taxable non-dividend income exactly as the user wrote it.",
    )
    student_loan_plan: str | None = Field(
        None,
        description="Student loan plan, for example plan1, plan2, plan4, plan5 or postgraduate.",
    )
    company_profit: str | None = Field(
        None,
        description="Company profit before director pay, exactly as the user wrote it.",
    )
    director_salary: str | None = Field(
        None,
        description="Director salary exactly as the user wrote it.",
    )
    distributable_reserves: str | None = Field(
        None,
        description=(
            "Retained company profit available for dividends before this "
            "year, exactly as the user wrote it."
        ),
    )
    savings_amount: str | None = Field(
        None,
        description=(
            "Amount to invest exactly as the user wrote it, for example '10,000'."
        ),
    )
    annual_growth_rate: str | None = Field(
        None,
        description=(
            "Expected annual growth rate as a decimal, for example 0.05 for 5%."
        ),
    )
    investment_years: str | None = Field(
        None,
        description=(
            "Number of years the money stays invested, exactly as the user wrote it."
        ),
    )
    scottish_taxpayer: bool | None = None
    pension_rate: str | None = Field(
        None,
        description="Pension contribution rate as a decimal, for example 0.06 for 6%.",
    )


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, str | int | bool | None] = Field(default_factory=dict)


class AgentDecision(BaseModel):
    action: Literal["call_tools", "ask", "respond"]
    tool_calls: list[ToolCall] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    message: str = ""
