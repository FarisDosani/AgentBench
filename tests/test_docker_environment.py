import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.docker_environment import DockerEnvironment


def test_constructor_validation(tmp_path: Path) -> None:
    assert DockerEnvironment(tmp_path).workspace_path == tmp_path.resolve()
    with pytest.raises(FileNotFoundError):
        DockerEnvironment(tmp_path / "missing")
    file_path = tmp_path / "file"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        DockerEnvironment(file_path)
    with pytest.raises(ValueError):
        DockerEnvironment(tmp_path, timeout_seconds=0)


def test_docker_available_true_and_false(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    assert DockerEnvironment(tmp_path).is_docker_available() is True

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    assert DockerEnvironment(tmp_path).is_docker_available() is False

    def unavailable(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", unavailable)
    assert DockerEnvironment(tmp_path).is_docker_available() is False


def test_build_command_and_unavailable_error(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    environment = DockerEnvironment(tmp_path, image="custom-image")
    environment.build_image()
    build_command, build_kwargs = calls[1]
    assert build_command[:2] == ["docker", "build"]
    assert "agentbench-python.Dockerfile" in build_command[3]
    assert ["-t", "custom-image"] == build_command[4:6]
    assert build_kwargs.get("shell") is not True

    monkeypatch.setattr(environment, "is_docker_available", lambda: False)
    with pytest.raises(RuntimeError, match="unavailable"):
        environment.build_image()


def test_run_command_is_isolated_and_returns_output(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=2, stdout="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = DockerEnvironment(tmp_path).run_command(["pytest", "-q"])
    command = captured["command"]

    assert command[:3] == ["docker", "run", "--rm"]
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--memory") + 1] == "512m"
    assert command[command.index("--cpus") + 1] == "1"
    assert command[command.index("--workdir") + 1] == "/workspace"
    assert f"source={tmp_path.resolve()}" in command[command.index("--mount") + 1]
    assert command[-2:] == ["pytest", "-q"]
    assert "--privileged" not in command
    assert "/var/run/docker.sock" not in " ".join(command)
    assert captured["kwargs"].get("shell") is not True
    assert result.exit_code == 2
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.timed_out is False
    assert result.duration_ms >= 0


def test_run_command_timeout(tmp_path: Path, monkeypatch) -> None:
    def timeout(*args: Any, **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(args[0], 1, output=b"partial", stderr=b"late")

    monkeypatch.setattr(subprocess, "run", timeout)
    result = DockerEnvironment(tmp_path, timeout_seconds=1).run_command(["pytest"])

    assert result.exit_code == -1
    assert result.stdout == "partial"
    assert result.stderr == "late"
    assert result.timed_out is True
