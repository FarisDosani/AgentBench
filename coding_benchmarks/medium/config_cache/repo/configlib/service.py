from pathlib import Path

from configlib.parser import parse_config


class ConfigService:
    def __init__(self) -> None:
        self._cache: dict[Path, dict[str, str]] = {}

    def load(self, path: str | Path) -> dict[str, str]:
        config_path = Path(path)
        if config_path not in self._cache:
            self._cache[config_path] = parse_config(config_path.read_text(encoding="utf-8"))
        return self._cache[config_path]
