from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvaluationResult(BaseModel):
    task_id: NonEmptyStr
    agent_name: NonEmptyStr
    score: Annotated[float, Field(ge=0.0, le=1.0)]
    passed: bool
    reason: str | None = None
