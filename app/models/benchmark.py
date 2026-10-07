from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.evaluation import EvaluationResult
from app.models.result import AgentRunResult


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class BenchmarkTaskResult(BaseModel):
    run_result: AgentRunResult
    evaluation: EvaluationResult


class BenchmarkRunResult(BaseModel):
    agent_name: NonEmptyStr
    total_tasks: Annotated[int, Field(ge=0)]
    passed_tasks: Annotated[int, Field(ge=0)]
    failed_tasks: Annotated[int, Field(ge=0)]
    average_score: Annotated[float, Field(ge=0.0, le=1.0)]
    average_latency_ms: Annotated[float, Field(ge=0.0)]
    results: list[BenchmarkTaskResult]
