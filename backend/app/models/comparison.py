from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AgentComparisonSummary(BaseModel):
    rank: Annotated[int, Field(gt=0)]
    agent_name: NonEmptyStr
    average_score: Annotated[float, Field(ge=0.0, le=1.0)]
    average_latency_ms: Annotated[float, Field(ge=0.0)]
    passed_tasks: Annotated[int, Field(ge=0)]
    failed_tasks: Annotated[int, Field(ge=0)]
    total_tasks: Annotated[int, Field(ge=0)]


class ComparisonResult(BaseModel):
    summaries: list[AgentComparisonSummary]
    best_agent: str | None
    report: str
