import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.coding_task import CodingTask, TaskDifficulty
from app.services.coding_task_loader import CodingTaskLoader


def config_data(repository_path: str = "repo", task_id: str = "task-1") -> dict[str, object]:
    return {
        "id": task_id,
        "name": "Loader task",
        "description": "Fix the fixture implementation.",
        "repository_path": repository_path,
        "difficulty": "medium",
        "visible_test_command": "pytest -q tests",
        "hidden_test_command": "pytest -q hidden_tests",
        "allowed_tools": ["list_files", "read_file", "search_repo", "write_file"],
        "timeout_seconds": 120,
        "expected_files_changed": ["src.py"],
        "metadata": {"category": "loader-test"},
    }


def write_config(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_valid_task_and_resolve_relative_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    config = tmp_path / "task.json"
    write_config(config, config_data())

    task = CodingTaskLoader.load_file(config)

    assert isinstance(task, CodingTask)
    assert task.difficulty is TaskDifficulty.MEDIUM
    assert Path(task.repository_path) == repository.resolve()


def test_directory_ordering_and_non_json_ignored(tmp_path: Path) -> None:
    for directory_name, task_id in [("b", "second"), ("a", "first")]:
        directory = tmp_path / directory_name
        directory.mkdir()
        (directory / "repo").mkdir()
        write_config(directory / "task.json", config_data(task_id=task_id))
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    assert [task.id for task in CodingTaskLoader.load_directory(tmp_path)] == [
        "first",
        "second",
    ]


def test_invalid_config_and_missing_repository_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    write_config(invalid, {"id": "incomplete"})
    with pytest.raises(ValidationError):
        CodingTaskLoader.load_file(invalid)

    missing = tmp_path / "missing.json"
    write_config(missing, config_data(repository_path="missing-repo"))
    with pytest.raises(FileNotFoundError):
        CodingTaskLoader.load_file(missing)


def test_missing_config_and_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        CodingTaskLoader.load_file(tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        CodingTaskLoader.load_directory(tmp_path / "missing")


def test_all_shipped_coding_benchmarks_are_complete() -> None:
    benchmark_root = Path(__file__).resolve().parents[1] / "coding_benchmarks"
    tasks = CodingTaskLoader.load_directory(benchmark_root)

    assert len(tasks) >= 6
    assert {task.difficulty for task in tasks} == {
        TaskDifficulty.EASY,
        TaskDifficulty.MEDIUM,
        TaskDifficulty.HARD,
    }
    assert all(Path(task.repository_path).is_dir() for task in tasks)
    assert all((Path(task.repository_path) / "tests").is_dir() for task in tasks)
    assert all((Path(task.repository_path) / "hidden_tests").is_dir() for task in tasks)
    assert all(task.visible_test_command.startswith("pytest") for task in tasks)
    assert all(task.is_hidden_test_enabled for task in tasks)
