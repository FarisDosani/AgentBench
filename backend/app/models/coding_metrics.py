from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class FailureCategory(str, Enum):
    NONE = "none"
    AGENT_ERROR = "agent_error"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"
    VISIBLE_TEST_FAILURE = "visible_test_failure"
    HIDDEN_TEST_FAILURE = "hidden_test_failure"
    REGRESSION = "regression"
    MALFORMED_RESPONSE = "malformed_response"
    MAX_ITERATIONS = "max_iterations"
    REVIEWER_REJECTION = "reviewer_rejection"
    UNKNOWN = "unknown"


class CodingMetrics(BaseModel):
    task_success: bool
    regression_detected: bool
    tool_calls: NonNegativeInt
    runtime_ms: NonNegativeFloat
    prompt_tokens: NonNegativeInt | None = None
    completion_tokens: NonNegativeInt | None = None
    total_tokens: NonNegativeInt | None = None
    estimated_cost_usd: NonNegativeFloat | None = None
    files_changed: NonNegativeInt
    lines_added: NonNegativeInt
    lines_removed: NonNegativeInt
    patch_size: NonNegativeInt
    failure_category: FailureCategory
