import json
from pathlib import Path


class JsonFlagStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, bool]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, flags: dict[str, bool]) -> None:
        self.path.write_text(json.dumps(flags, sort_keys=True), encoding="utf-8")
