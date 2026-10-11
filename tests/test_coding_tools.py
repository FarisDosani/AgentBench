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
    with pytest.raises(PermissionError):
        tools.execute("run_tests")


def test_toolset_preserves_workspace_boundary(tmp_path: Path) -> None:
    tools = CodingToolset(RepositoryWorkspace(tmp_path), ["read_file", "write_file"])
    with pytest.raises(ValueError):
        tools.execute("read_file", relative_path="../secret.txt")
    with pytest.raises(ValueError):
        tools.execute("write_file", relative_path="C:\\secret.txt", content="x")


def test_hidden_tests_are_not_exposed_by_coding_tools(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("public needle", encoding="utf-8")
    hidden_directory = tmp_path / "hidden_tests"
    hidden_directory.mkdir()
    (hidden_directory / "test_secret.py").write_text(
        "secret needle", encoding="utf-8"
    )
    tools = CodingToolset(
        RepositoryWorkspace(tmp_path),
        ["list_files", "read_file", "search_repo", "write_file"],
    )

    assert tools.execute("list_files") == ["source.py"]
    assert tools.execute("search_repo", query="needle") == [
        {"path": "source.py", "line_number": 1, "line": "public needle"}
    ]
    with pytest.raises(PermissionError, match="Hidden tests"):
        tools.execute("read_file", relative_path="hidden_tests/test_secret.py")
    with pytest.raises(PermissionError, match="Hidden tests"):
        tools.execute(
            "write_file",
            relative_path="hidden_tests/test_secret.py",
            content="changed",
        )


def test_visible_benchmark_tests_can_be_read_but_not_modified(tmp_path: Path) -> None:
    visible_directory = tmp_path / "tests"
    visible_directory.mkdir()
    visible_test = visible_directory / "test_public.py"
    visible_test.write_text("def test_public(): pass", encoding="utf-8")
    tools = CodingToolset(
        RepositoryWorkspace(tmp_path),
        ["list_files", "read_file", "write_file"],
    )

    assert "tests/test_public.py" in tools.execute("list_files")
    assert "test_public" in tools.execute(
        "read_file", relative_path="tests/test_public.py"
    )
    with pytest.raises(PermissionError, match="read-only"):
        tools.execute(
            "write_file",
            relative_path="tests/test_public.py",
            content="def test_public(): assert True",
        )
    assert visible_test.read_text(encoding="utf-8") == "def test_public(): pass"


def test_run_tests_is_available_only_when_allowed_and_configured(
    tmp_path: Path,
) -> None:
    calls = 0

    def run_visible_tests() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "exit_code": 0,
            "passed": True,
            "timed_out": False,
            "stdout": "2 passed",
            "stderr": "",
        }

    tools = CodingToolset(
        RepositoryWorkspace(tmp_path),
        ["run_tests"],
        run_tests_callback=run_visible_tests,
    )

    assert tools.has_tool("run_tests") is True
    assert tools.execute("run_tests") == {
        "exit_code": 0,
        "passed": True,
        "timed_out": False,
        "stdout": "2 passed",
        "stderr": "",
    }
    assert calls == 1

    disallowed = CodingToolset(
        RepositoryWorkspace(tmp_path),
        ["read_file"],
        run_tests_callback=run_visible_tests,
    )
    assert disallowed.has_tool("run_tests") is False
    with pytest.raises(PermissionError):
        disallowed.execute("run_tests")

    unconfigured = CodingToolset(RepositoryWorkspace(tmp_path), ["run_tests"])
    assert unconfigured.has_tool("run_tests") is False
    with pytest.raises(RuntimeError, match="not configured"):
        unconfigured.execute("run_tests")


def test_run_tests_rejects_model_supplied_command_without_calling_callback(
    tmp_path: Path,
) -> None:
    called = False

    def run_visible_tests() -> object:
        nonlocal called
        called = True
        return {}

    tools = CodingToolset(
        RepositoryWorkspace(tmp_path),
        ["run_tests"],
        run_tests_callback=run_visible_tests,
    )

    with pytest.raises(ValueError, match="does not accept arguments"):
        tools.execute("run_tests", command="pytest hidden_tests")
    assert called is False
