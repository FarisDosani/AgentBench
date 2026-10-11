import json

import pytest
from pydantic import ValidationError

from app.models.task import BenchmarkTask
from app.services.task_loader import TaskLoader


def task_data(task_id: str, name: str) -> dict[str, str]:
    return {
        "id": task_id,
        "name": name,
        "description": "Test description",
        "input": "Test input",
    }


def test_valid_file_loads_tasks_in_order(tmp_path) -> None:
    task_file = tmp_path / "tasks.json"
    task_file.write_text(
        json.dumps([task_data("first", "First"), task_data("second", "Second")]),
        encoding="utf-8",
    )

    tasks = TaskLoader.load_file(task_file)

    assert all(isinstance(task, BenchmarkTask) for task in tasks)
    assert [task.id for task in tasks] == ["first", "second"]


def test_load_file_accepts_string_path(tmp_path) -> None:
    task_file = tmp_path / "tasks.json"
    task_file.write_text(json.dumps([task_data("one", "One")]), encoding="utf-8")

    assert TaskLoader.load_file(str(task_file))[0].id == "one"


def test_invalid_json_fails(tmp_path) -> None:
    task_file = tmp_path / "invalid.json"
    task_file.write_text("{invalid", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        TaskLoader.load_file(task_file)


def test_non_list_top_level_rejected(tmp_path) -> None:
    task_file = tmp_path / "tasks.json"
    task_file.write_text(json.dumps(task_data("one", "One")), encoding="utf-8")

    with pytest.raises(ValueError):
        TaskLoader.load_file(task_file)


def test_invalid_task_rejected(tmp_path) -> None:
    task_file = tmp_path / "tasks.json"
    task_file.write_text(json.dumps([task_data("", "Invalid")]), encoding="utf-8")

    with pytest.raises(ValidationError):
        TaskLoader.load_file(task_file)


def test_missing_file_rejected(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        TaskLoader.load_file(tmp_path / "missing.json")


def test_directory_loads_json_files_in_filename_order_and_ignores_other_files(
    tmp_path,
) -> None:
    (tmp_path / "b.json").write_text(
        json.dumps([task_data("second", "Second")]), encoding="utf-8"
    )
    (tmp_path / "a.json").write_text(
        json.dumps([task_data("first", "First")]), encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("not JSON", encoding="utf-8")

    tasks = TaskLoader.load_directory(tmp_path)

    assert [task.id for task in tasks] == ["first", "second"]


def test_missing_directory_rejected(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        TaskLoader.load_directory(tmp_path / "missing")
