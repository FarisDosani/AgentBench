import os
from pathlib import Path, PureWindowsPath


IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
}


class RepositoryWorkspace:
    def __init__(self, root_path: str | Path) -> None:
        root = Path(root_path)
        if not root.exists():
            raise FileNotFoundError(root)
        if not root.is_dir():
            raise ValueError("Workspace root must be a directory")
        self.root_path = root.resolve()

    def resolve_path(self, relative_path: str | Path) -> Path:
        raw_path = str(relative_path)
        path = Path(relative_path)
        windows_path = PureWindowsPath(raw_path)
        if path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
            raise ValueError("Workspace paths must be relative")

        resolved = (self.root_path / path).resolve()
        if not resolved.is_relative_to(self.root_path):
            raise ValueError("Path escapes the repository workspace")
        return resolved

    def list_files(self) -> list[str]:
        files: list[str] = []
        for current_root, directories, filenames in os.walk(
            self.root_path, followlinks=False
        ):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in IGNORED_DIRECTORIES
            )
            for filename in sorted(filenames):
                path = Path(current_root) / filename
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved.is_relative_to(self.root_path) and resolved.is_file():
                    files.append(path.relative_to(self.root_path).as_posix())
        return sorted(files)

    def read_file(self, relative_path: str | Path) -> str:
        path = self.resolve_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            raise ValueError("Cannot read a directory")
        return path.read_text(encoding="utf-8")

    def write_file(self, relative_path: str | Path, content: str) -> None:
        path = self.resolve_path(relative_path)
        if path.exists() and path.is_dir():
            raise ValueError("Cannot write to a directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def search_repo(self, query: str) -> list[dict[str, object]]:
        if not query:
            raise ValueError("Search query must not be empty")

        matches: list[dict[str, object]] = []
        for relative_path in self.list_files():
            try:
                content = self.read_file(relative_path)
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(content.splitlines(), start=1):
                if query in line:
                    matches.append(
                        {
                            "path": relative_path,
                            "line_number": line_number,
                            "line": line,
                        }
                    )
        return matches
