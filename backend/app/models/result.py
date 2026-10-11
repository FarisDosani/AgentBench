from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AgentRunResult(BaseModel):
    agent_name: NonEmptyStr
    task_id: NonEmptyStr
    output: str | None = None
    success: bool
    latency_ms: Annotated[float, Field(ge=0)]
    error: str | None = None
