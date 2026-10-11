import json
from pathlib import Path

from app.models.task import BenchmarkTask


class TaskLoader:
    @staticmethod
    def load_file(path: str | Path) -> list[BenchmarkTask]:
        file_path = Path(path)

        with file_path.open(encoding="utf-8") as task_file:
            data = json.load(task_file)

        if not isinstance(data, list):
            raise ValueError("Task file must contain a top-level JSON list")

        return [BenchmarkTask.model_validate(item) for item in data]

    @classmethod
    def load_directory(cls, path: str | Path) -> list[BenchmarkTask]:
        directory_path = Path(path)
        if not directory_path.exists():
            raise FileNotFoundError(directory_path)

        tasks: list[BenchmarkTask] = []
        for file_path in sorted(directory_path.glob("*.json"), key=lambda item: item.name):
            tasks.extend(cls.load_file(file_path))
        return tasks
