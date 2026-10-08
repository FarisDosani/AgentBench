from typing import Annotated

from pydantic import BaseModel, Field


class DockerCommandResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: Annotated[float, Field(ge=0)]
