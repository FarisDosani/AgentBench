from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AgentConfig(BaseModel):
    name: NonEmptyStr
    model: NonEmptyStr
    system_prompt: str | None = None
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    max_tokens: Annotated[int, Field(gt=0)] = 1024
    tools: list[str] = Field(default_factory=list)
