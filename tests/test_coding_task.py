from typing import Any

import pytest
from pydantic import ValidationError

from app.models.coding_task import CodingTask, TaskDifficulty


def make_task(**overrides: Any) -> CodingTask:
    values: dict[str, Any] = {
        "id": "coding-1",
        "name": "Fix the parser",
        "description": "Correct parsing of empty input.",
        "repository_path": "repos/parser",
        "difficulty": "easy",
        "visible_test_command": "pytest tests/test_parser.py",
    }
    values.update(overrides)
    return CodingTask(**values)


@pytest.mark.parametrize(
    ("difficulty", "expected"),
    [
        ("easy", TaskDifficulty.EASY),
        ("medium", TaskDifficulty.MEDIUM),
        ("hard", TaskDifficulty.HARD),
    ],
)
def test_valid_difficulty_levels_parse_to_enum(
    difficulty: str,
    expected: TaskDifficulty,
) -> None:
    task = make_task(difficulty=difficulty)

    assert task.difficulty is expected


def test_invalid_difficulty_rejected() -> None:
    with pytest.raises(ValidationError):
        make_task(difficulty="expert")


@pytest.mark.parametrize(
    "field",
    ["id", "name", "description", "repository_path", "visible_test_command"],
)
def test_required_empty_fields_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        make_task(**{field: "   "})


@pytest.mark.parametrize("timeout", [0, -1])
def test_non_positive_timeout_rejected(timeout: int) -> None:
    with pytest.raises(ValidationError):
        make_task(timeout_seconds=timeout)


def test_default_allowed_tools_are_correct() -> None:
    assert make_task().allowed_tools == [
        "read_file",
        "list_files",
        "search_repo",
        "write_file",
        "run_tests",
    ]


def test_custom_allowed_tools_accepted() -> None:
    assert make_task(allowed_tools=["read_file", "run_tests"]).allowed_tools == [
        "read_file",
        "run_tests",
    ]


def test_duplicate_tools_rejected() -> None:
    with pytest.raises(ValidationError):
        make_task(allowed_tools=["read_file", "read_file"])


def test_empty_tool_name_rejected() -> None:
    with pytest.raises(ValidationError):
        make_task(allowed_tools=["read_file", "   "])


def test_mutable_defaults_are_independent() -> None:
    first = make_task(id="first")
    second = make_task(id="second")

    first.allowed_tools.append("custom_tool")
    first.expected_files_changed.append("app/parser.py")
    first.metadata["issue"] = "123"

    assert "custom_tool" not in second.allowed_tools
    assert second.expected_files_changed == []
    assert second.metadata == {}


@pytest.mark.parametrize(
    ("command", "enabled"),
    [("pytest tests/hidden", True), (None, False), ("   ", False)],
)
def test_hidden_test_detection(command: str | None, enabled: bool) -> None:
    assert make_task(hidden_test_command=command).is_hidden_test_enabled is enabled


def test_expected_files_changed_supported() -> None:
    files = ["app/parser.py", "tests/test_parser.py"]

    assert make_task(expected_files_changed=files).expected_files_changed == files


def test_metadata_supported() -> None:
    metadata = {"source": "internal", "issue": "123"}

    assert make_task(metadata=metadata).metadata == metadata
