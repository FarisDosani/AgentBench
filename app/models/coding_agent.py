from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: dict[str, object]
    success: bool
    output: str | None = None
    error: str | None = None


class CodingAgentResult(BaseModel):
    task_id: NonEmptyStr
    agent_name: NonEmptyStr
    success: bool
    final_answer: str | None
    tool_calls: list[ToolCallRecord]
    iterations: Annotated[int, Field(ge=0)]
    latency_ms: Annotated[float, Field(ge=0)]
    error: str | None = None
