from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ToolExecutionResult(BaseModel):
    tool_name: NonEmptyStr
    success: bool
    output: str | None = None
    error: str | None = None
    latency_ms: Annotated[float, Field(ge=0)]
