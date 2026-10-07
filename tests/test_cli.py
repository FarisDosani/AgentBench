from pathlib import Path
from typing import Any

from app import cli
from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask


def make_task() -> BenchmarkTask:
    return BenchmarkTask(
        id="task-1",
        name="CLI task",
        description="A task used by CLI tests.",
        input="Return expected.",
        expected_output="expected",
    )


def test_run_command_uses_defaults_executes_saves_and_prints_summary(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, Any] = {"calls": 0}

    def load_directory(path: str) -> list[BenchmarkTask]:
        captured["benchmark_path"] = path
        return [make_task()]

    def fake_executor(agent: AgentConfig, task: BenchmarkTask) -> str:
        captured["calls"] += 1
        captured["agent"] = agent
        return "expected"

    monkeypatch.setattr(cli.TaskLoader, "load_directory", load_directory)
    monkeypatch.setattr(cli, "OmniRouteExecutor", lambda: fake_executor)

    exit_code = cli.main(
        ["run", "--name", "Agent A", "--model", "MODEL_ID"]
    )

    agent = captured["agent"]
    assert exit_code == 0
    assert captured["benchmark_path"] == "benchmarks"
    assert captured["calls"] == 1
    assert agent.name == "Agent A"
    assert agent.model == "MODEL_ID"
    assert agent.system_prompt is None
    assert agent.temperature == 0.0
    assert agent.max_tokens == 1024
    assert len(list((tmp_path / "results").glob("*.json"))) == 1

    output = capsys.readouterr().out
    assert "Agent: Agent A" in output
    assert "Model: MODEL_ID" in output
    assert "Total tasks: 1" in output
    assert "Passed tasks: 1" in output
    assert "Failed tasks: 0" in output
    assert "Saved result:" in output


def test_run_command_applies_custom_values_and_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark_path = tmp_path / "custom-benchmarks"
    results_path = tmp_path / "custom-results"
    captured: dict[str, Any] = {}

    def load_directory(path: str) -> list[BenchmarkTask]:
        captured["benchmark_path"] = path
        return [make_task()]

    def fake_executor(agent: AgentConfig, task: BenchmarkTask) -> str:
        captured["agent"] = agent
        return "expected"

    monkeypatch.setattr(cli.TaskLoader, "load_directory", load_directory)
    monkeypatch.setattr(cli, "OmniRouteExecutor", lambda: fake_executor)

    exit_code = cli.main(
        [
            "run",
            "--name",
            "Custom Agent",
            "--model",
            "custom-model",
            "--system-prompt",
            "Follow the task.",
            "--temperature",
            "0.7",
            "--max-tokens",
            "256",
            "--benchmarks",
            str(benchmark_path),
            "--results",
            str(results_path),
        ]
    )

    agent = captured["agent"]
    assert exit_code == 0
    assert captured["benchmark_path"] == str(benchmark_path)
    assert agent.name == "Custom Agent"
    assert agent.model == "custom-model"
    assert agent.system_prompt == "Follow the task."
    assert agent.temperature == 0.7
    assert agent.max_tokens == 256
    assert len(list(results_path.glob("*.json"))) == 1
