import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.models.benchmark import BenchmarkRunResult


class ResultStore:
    def __init__(self, directory: str | Path = "results") -> None:
        self.directory = Path(directory)

    def save(
        self,
        result: BenchmarkRunResult,
        filename: str | None = None,
    ) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)

        if filename is None:
            agent_name = result.agent_name.lower().replace(" ", "_")
            agent_name = re.sub(r"[^a-z0-9_-]+", "_", agent_name)
            agent_name = re.sub(r"_+", "_", agent_name).strip("_-") or "agent"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"{agent_name}_{timestamp}.json"
        elif not filename.endswith(".json"):
            filename = f"{filename}.json"

        saved_path = self.directory / filename
        with saved_path.open("w", encoding="utf-8") as result_file:
            json.dump(
                result.model_dump(mode="json"),
                result_file,
                indent=2,
                ensure_ascii=False,
            )

        return saved_path

    @staticmethod
    def load(path: str | Path) -> BenchmarkRunResult:
        result_path = Path(path)
        with result_path.open(encoding="utf-8") as result_file:
            data = json.load(result_file)
        return BenchmarkRunResult.model_validate(data)

    def list_results(self) -> list[Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        return sorted(self.directory.glob("*.json"), key=lambda path: path.name)
