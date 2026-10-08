from typing import Annotated

from pydantic import BaseModel, Field


class TestCommandResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    timed_out: bool
    duration_ms: Annotated[float, Field(ge=0)]


class CodingTestResult(BaseModel):
    visible: TestCommandResult
    hidden: TestCommandResult | None
    visible_passed: bool
    hidden_passed: bool | None
    all_passed: bool
    regression_detected: bool
