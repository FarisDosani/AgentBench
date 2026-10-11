from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.coding_agent import CodingAgentResult
from app.models.test_result import CodingTestResult


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReviewResult(BaseModel):
    approved: bool
    feedback: NonEmptyStr
    requested_changes: list[str] = Field(default_factory=list)


class ReviewerStrategyResult(BaseModel):
    strategy_name: str
    task_id: str
    agent_results: list[CodingAgentResult]
    reviews: list[ReviewResult]
    test_result: CodingTestResult
    success: bool
