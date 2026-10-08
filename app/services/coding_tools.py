from typing import Any

from app.services.repository_workspace import RepositoryWorkspace


SUPPORTED_TOOLS = {"list_files", "read_file", "search_repo", "write_file"}


class CodingToolset:
    def __init__(
        self,
        workspace: RepositoryWorkspace,
        allowed_tools: list[str],
    ) -> None:
        self.workspace = workspace
        self.allowed_tools = set(allowed_tools)

    def has_tool(self, name: str) -> bool:
        return name in SUPPORTED_TOOLS and name in self.allowed_tools

    def execute(self, name: str, **kwargs: Any) -> Any:
        if name not in SUPPORTED_TOOLS:
            raise KeyError(name)
        if name not in self.allowed_tools:
            raise PermissionError(f"Tool is not allowed: {name}")

        if name == "list_files":
            return self.workspace.list_files()
        if name == "read_file":
            return self.workspace.read_file(**kwargs)
        if name == "search_repo":
            return self.workspace.search_repo(**kwargs)
        return self.workspace.write_file(**kwargs)
