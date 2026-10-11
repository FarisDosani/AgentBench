from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CodingTask(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    repository_path: NonEmptyStr
    difficulty: TaskDifficulty
    visible_test_command: NonEmptyStr
    hidden_test_command: str | None = None
    allowed_tools: list[NonEmptyStr] = Field(
        default_factory=lambda: [
            "read_file",
            "list_files",
            "search_repo",
            "write_file",
            "run_tests",
        ]
    )
    timeout_seconds: Annotated[int, Field(gt=0)] = 300
    expected_files_changed: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("allowed_tools")
    @classmethod
    def validate_unique_tools(cls, tools: list[str]) -> list[str]:
        if len(tools) != len(set(tools)):
            raise ValueError("allowed_tools must not contain duplicates")
        return tools

    @property
    def is_hidden_test_enabled(self) -> bool:
        return self.hidden_test_command is not None and bool(
            self.hidden_test_command.strip()
        )
