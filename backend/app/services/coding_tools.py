from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from app.services.repository_workspace import RepositoryWorkspace


SUPPORTED_TOOLS = {
    "list_files",
    "read_file",
    "search_repo",
    "write_file",
    "run_tests",
}
HIDDEN_TEST_DIRECTORY = "hidden_tests"
VISIBLE_TEST_DIRECTORY = "tests"


class CodingToolset:
    def __init__(
        self,
        workspace: RepositoryWorkspace,
        allowed_tools: list[str],
        run_tests_callback: Callable[[], object] | None = None,
    ) -> None:
        self.workspace = workspace
        self.allowed_tools = set(allowed_tools)
        self.run_tests_callback = run_tests_callback

    def has_tool(self, name: str) -> bool:
        if name == "run_tests":
            return name in self.allowed_tools and self.run_tests_callback is not None
        return name in SUPPORTED_TOOLS and name in self.allowed_tools

    def execute(self, name: str, **kwargs: Any) -> Any:
        if name not in SUPPORTED_TOOLS:
            raise KeyError(name)
        if name not in self.allowed_tools:
            raise PermissionError(f"Tool is not allowed: {name}")

        if name == "run_tests":
            if kwargs:
                raise ValueError("run_tests does not accept arguments")
            if self.run_tests_callback is None:
                raise RuntimeError("run_tests is not configured")
            return self.run_tests_callback()
        if name == "list_files":
            return [
                path
                for path in self.workspace.list_files()
                if not self._is_hidden_test_path(path)
            ]
        if name == "read_file":
            self._reject_hidden_test_path(kwargs.get("relative_path"))
            return self.workspace.read_file(**kwargs)
        if name == "search_repo":
            return self._search_visible_files(**kwargs)
        self._reject_hidden_test_path(kwargs.get("relative_path"))
        self._reject_visible_test_write(kwargs.get("relative_path"))
        return self.workspace.write_file(**kwargs)

    @staticmethod
    def _is_hidden_test_path(relative_path: object) -> bool:
        if not isinstance(relative_path, (str, PurePosixPath)):
            return False
        normalized = str(relative_path).replace("\\", "/")
        return HIDDEN_TEST_DIRECTORY in PurePosixPath(normalized).parts

    def _reject_hidden_test_path(self, relative_path: object) -> None:
        if self._is_hidden_test_path(relative_path):
            raise PermissionError("Hidden tests are not accessible to coding tools")

    @staticmethod
    def _reject_visible_test_write(relative_path: object) -> None:
        if not isinstance(relative_path, (str, PurePosixPath)):
            return
        normalized = str(relative_path).replace("\\", "/")
        if VISIBLE_TEST_DIRECTORY in PurePosixPath(normalized).parts:
            raise PermissionError("Visible benchmark tests are read-only")

    def _search_visible_files(self, query: str) -> list[dict[str, object]]:
        if not query:
            raise ValueError("Search query must not be empty")

        matches: list[dict[str, object]] = []
        for relative_path in self.workspace.list_files():
            if self._is_hidden_test_path(relative_path):
                continue
            try:
                content = self.workspace.read_file(relative_path)
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
