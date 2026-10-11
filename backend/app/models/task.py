from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class BenchmarkTask(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    input: NonEmptyStr
    expected_output: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    timeout_seconds: Annotated[int, Field(gt=0)] = 60
