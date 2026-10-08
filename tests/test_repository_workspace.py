from pathlib import Path

import pytest

from app.services.repository_workspace import RepositoryWorkspace


def test_workspace_validation(tmp_path: Path) -> None:
    assert RepositoryWorkspace(tmp_path).root_path == tmp_path.resolve()
    with pytest.raises(FileNotFoundError):
        RepositoryWorkspace(tmp_path / "missing")
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        RepositoryWorkspace(file_path)


def test_recursive_listing_is_sorted_and_ignores_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.py").write_text("b", encoding="utf-8")
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    for ignored in [".git", "__pycache__", ".pytest_cache", "node_modules", "venv", ".venv"]:
        directory = tmp_path / ignored
        directory.mkdir()
        (directory / "ignored.txt").write_text("ignored", encoding="utf-8")

    assert RepositoryWorkspace(tmp_path).list_files() == ["a.py", "src/b.py"]


def test_read_write_create_and_nested_files(tmp_path: Path) -> None:
    workspace = RepositoryWorkspace(tmp_path)
    workspace.write_file("src/new.py", "first")
    assert workspace.read_file("src/new.py") == "first"
    workspace.write_file("src/new.py", "second")
    assert workspace.read_file("src/new.py") == "second"
    with pytest.raises(FileNotFoundError):
        workspace.read_file("missing.py")
    with pytest.raises(ValueError):
        workspace.read_file("src")


@pytest.mark.parametrize(
    "path",
    ["../outside.txt", "/tmp/outside.txt", "C:\\outside.txt", "D:/outside.txt"],
)
def test_unsafe_paths_are_rejected(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        RepositoryWorkspace(tmp_path).resolve_path(path)


def test_symlink_escape_rejected_when_supported(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are not available")

    with pytest.raises(ValueError):
        RepositoryWorkspace(tmp_path).resolve_path("escape/file.txt")


def test_search_returns_deterministic_matches_and_line_numbers(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("none\nneedle two", encoding="utf-8")
    (tmp_path / "a.txt").write_text("needle one\nnone", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\xff\xfe")

    assert RepositoryWorkspace(tmp_path).search_repo("needle") == [
        {"path": "a.txt", "line_number": 1, "line": "needle one"},
        {"path": "b.txt", "line_number": 2, "line": "needle two"},
    ]


def test_empty_search_query_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        RepositoryWorkspace(tmp_path).search_repo("")
