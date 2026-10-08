from pathlib import Path

from app import cli
from app.models.coding_benchmark_run import (
    CodingBenchmarkRunResult,
    StrategyBenchmarkResult,
)
from app.models.coding_metrics import CodingMetrics, FailureCategory
from app.models.coding_task import CodingTask
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult


def make_task(tmp_path: Path) -> CodingTask:
    repository = tmp_path / "repo"
    repository.mkdir(exist_ok=True)
    return CodingTask(
        id="easy-task",
        name="Easy task",
        description="Fix it.",
        repository_path=str(repository),
        difficulty="easy",
        visible_test_command="pytest tests",
        hidden_test_command="pytest hidden_tests",
    )


def make_result(success: bool = True) -> CodingBenchmarkRunResult:
    command = CommandResult(
        command="pytest tests",
        exit_code=0 if success else 1,
        stdout="visible",
        stderr="",
        passed=success,
        timed_out=False,
        duration_ms=2,
    )
    tests = CodingTestResult(
        visible=command,
        hidden=None,
        visible_passed=success,
        hidden_passed=None,
        all_passed=success,
        regression_detected=False,
    )
    metrics = CodingMetrics(
        task_success=success,
        regression_detected=False,
        tool_calls=2,
        runtime_ms=5,
        files_changed=1,
        lines_added=3,
        lines_removed=1,
        patch_size=4,
        failure_category=FailureCategory.NONE if success else FailureCategory.AGENT_ERROR,
    )
    strategy = StrategyBenchmarkResult(
        strategy_name="direct",
        task_id="easy-task",
        success=success,
        test_result=tests,
        metrics=metrics,
        workspace_path="internal",
    )
    return CodingBenchmarkRunResult(
        task_id="easy-task",
        difficulty="easy",
        strategy_results=[strategy],
        best_strategy="direct",
    )


def install_cli_fakes(monkeypatch, tmp_path: Path, result: CodingBenchmarkRunResult):
    captured = {}
    monkeypatch.setattr(cli.CodingTaskLoader, "load_directory", lambda path: [make_task(tmp_path)])

    def adapter(provider: str, model: str):
        captured["provider"] = provider
        captured["model"] = model
        return object()

    class Factory:
        def __init__(self, llm, docker_image, max_iterations):
            captured["docker_image"] = docker_image
            captured["max_iterations"] = max_iterations
            self.direct = object()
            self.planner_executor = object()
            self.reviewer = object()

    class Runner:
        def __init__(self, *args, **kwargs):
            captured["keep_workspaces"] = kwargs["keep_workspaces"]

        def run_task(self, task, strategies):
            captured["strategies"] = strategies
            return result

    monkeypatch.setattr(cli, "create_coding_llm_adapter", adapter)
    monkeypatch.setattr(cli, "CodingStrategyFactory", Factory)
    monkeypatch.setattr(cli, "CodingBenchmarkRunner", Runner)
    return captured


def test_default_gemini_all_strategies_and_report(tmp_path: Path, monkeypatch, capsys) -> None:
    captured = install_cli_fakes(monkeypatch, tmp_path, make_result())
    exit_code = cli.main(
        ["coding-run", "--task", "easy-task", "--model", "gemini-model"]
    )

    assert exit_code == 0
    assert captured["provider"] == "gemini"
    assert captured["strategies"] is None
    output = capsys.readouterr().out
    for expected in [
        "Task: easy-task",
        "Difficulty: easy",
        "Strategy: direct",
        "Visible tests passed: True",
        "Hidden tests passed: None",
        "Regression detected: False",
        "Tool calls: 2",
        "Files changed: 1",
        "Lines added: 3",
        "Lines removed: 1",
        "Patch size: 4",
        "Failure category: none",
        "Best Strategy: direct",
    ]:
        assert expected in output


def test_explicit_omniroute_and_repeatable_comma_strategies(
    tmp_path: Path, monkeypatch
) -> None:
    captured = install_cli_fakes(monkeypatch, tmp_path, make_result())
    exit_code = cli.main(
        [
            "coding-run",
            "--task",
            "easy-task",
            "--provider",
            "omniroute",
            "--model",
            "model",
            "--strategy",
            "reviewer,direct",
            "--strategy",
            "planner_executor",
            "--docker-image",
            "custom",
            "--max-iterations",
            "9",
            "--keep-workspaces",
        ]
    )
    assert exit_code == 0
    assert captured["provider"] == "omniroute"
    assert captured["strategies"] == ["reviewer", "direct", "planner_executor"]
    assert captured["docker_image"] == "custom"
    assert captured["max_iterations"] == 9
    assert captured["keep_workspaces"] is True


def test_all_failed_returns_one(tmp_path: Path, monkeypatch) -> None:
    install_cli_fakes(monkeypatch, tmp_path, make_result(False))
    assert cli.main(["coding-run", "--task", "easy-task", "--model", "m"]) == 1


def test_missing_task_invalid_strategy_and_config_error_return_two(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli.CodingTaskLoader, "load_directory", lambda path: [])
    assert cli.main(["coding-run", "--task", "missing", "--model", "m"]) == 2
    assert "not found" in capsys.readouterr().err

    install_cli_fakes(monkeypatch, tmp_path, make_result())
    assert cli.main(
        ["coding-run", "--task", "easy-task", "--model", "m", "--strategy", "bad"]
    ) == 2

    monkeypatch.setattr(
        cli.CodingTaskLoader,
        "load_directory",
        lambda path: (_ for _ in ()).throw(ValueError("bad config")),
    )
    assert cli.main(["coding-run", "--task", "easy-task", "--model", "m"]) == 2


def test_existing_generic_run_dispatch_is_preserved(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_benchmark", lambda args: 7)
    assert cli.main(["run", "--name", "Agent", "--model", "model"]) == 7
