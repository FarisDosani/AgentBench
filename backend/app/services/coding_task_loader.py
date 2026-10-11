import json
from pathlib import Path

from app.models.coding_task import CodingTask


class CodingTaskLoader:
    @staticmethod
    def load_file(path: str | Path) -> CodingTask:
        config_path = Path(path)
        with config_path.open(encoding="utf-8") as config_file:
            data = json.load(config_file)

        task = CodingTask.model_validate(data)
        repository_path = Path(task.repository_path)
        if not repository_path.is_absolute():
            repository_path = config_path.parent / repository_path
        repository_path = repository_path.resolve()
        if not repository_path.exists():
            raise FileNotFoundError(repository_path)
        if not repository_path.is_dir():
            raise ValueError("Coding task repository_path must be a directory")

        return task.model_copy(update={"repository_path": str(repository_path)})

    @classmethod
    def load_directory(cls, path: str | Path) -> list[CodingTask]:
        directory = Path(path)
        if not directory.exists():
            raise FileNotFoundError(directory)
        if not directory.is_dir():
            raise ValueError("Coding task path must be a directory")

        config_files = sorted(
            directory.rglob("*.json"),
            key=lambda item: item.relative_to(directory).as_posix(),
        )
        return [cls.load_file(config_file) for config_file in config_files]
