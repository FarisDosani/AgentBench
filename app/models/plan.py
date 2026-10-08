from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models.coding_agent import CodingAgentResult
from app.models.test_result import CodingTestResult


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PlanStep(BaseModel):
    id: int
    description: NonEmptyStr
    completed: bool = False


class AgentPlan(BaseModel):
    task_id: NonEmptyStr
    summary: NonEmptyStr
    steps: Annotated[list[PlanStep], Field(min_length=1)]

    @field_validator("steps")
    @classmethod
    def validate_unique_step_ids(cls, steps: list[PlanStep]) -> list[PlanStep]:
        ids = [step.id for step in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan step IDs must be unique")
        return steps


class PlannerExecutorResult(BaseModel):
    strategy_name: str
    task_id: str
    plan: AgentPlan
    agent_results: list[CodingAgentResult]
    test_result: CodingTestResult
    success: bool
