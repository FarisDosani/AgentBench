from pathlib import Path

import pytest

from app.services.coding_tools import CodingToolset
from app.services.repository_workspace import RepositoryWorkspace


def test_all_tool_dispatch(tmp_path: Path) -> None:
    workspace = RepositoryWorkspace(tmp_path)
    tools = CodingToolset(
        workspace, ["list_files", "read_file", "search_repo", "write_file"]
    )

    assert tools.execute("write_file", relative_path="src/a.py", content="needle") is None
    assert tools.execute("list_files") == ["src/a.py"]
    assert tools.execute("read_file", relative_path="src/a.py") == "needle"
    assert tools.execute("search_repo", query="needle") == [
        {"path": "src/a.py", "line_number": 1, "line": "needle"}
    ]
    assert tools.has_tool("read_file") is True


def test_permission_and_unknown_tool_enforcement(tmp_path: Path) -> None:
    tools = CodingToolset(RepositoryWorkspace(tmp_path), ["read_file"])
    assert tools.has_tool("write_file") is False
    assert tools.has_tool("run_tests") is False
    with pytest.raises(PermissionError):
        tools.execute("write_file", relative_path="x", content="x")
    with pytest.raises(KeyError):
        tools.execute("run_tests")


def test_toolset_preserves_workspace_boundary(tmp_path: Path) -> None:
    tools = CodingToolset(RepositoryWorkspace(tmp_path), ["read_file", "write_file"])
    with pytest.raises(ValueError):
        tools.execute("read_file", relative_path="../secret.txt")
    with pytest.raises(ValueError):
        tools.execute("write_file", relative_path="C:\\secret.txt", content="x")
