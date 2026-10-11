from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from app.models.coding_agent import CodingAgentResult, ToolCallRecord
from app.models.coding_benchmark_run import StrategyBenchmarkResult
from app.models.coding_metrics import CodingMetrics, FailureCategory
from app.models.coding_task import CodingTask
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult
from scripts import validate_coding_benchmark as validation


def make_task(tmp_path: Path) -> CodingTask:
    repository = tmp_path / "fixture"
    repository.mkdir()
    (repository / "source.py").write_text("broken = True\n", encoding="utf-8")
    return CodingTask(
        id="easy-validation",
        name="Easy validation",
        description="Repair the fixture.",
        repository_path=str(repository),
        difficulty="easy",
        visible_test_command="pytest -q tests",
        hidden_test_command="pytest -q hidden_tests",
    )


def make_command(passed: bool, *, hidden: bool = False) -> CommandResult:
    return CommandResult(
        command="pytest -q hidden_tests" if hidden else "pytest -q tests",
        exit_code=0 if passed else 1,
        stdout="HIDDEN STDOUT SECRET" if hidden else "visible output",
        stderr="HIDDEN STDERR SECRET" if hidden else "",
        passed=passed,
        timed_out=False,
        duration_ms=1,
    )


def make_test_result(
    *,
    visible: bool,
    hidden: bool,
    regression: bool = False,
) -> CodingTestResult:
    return CodingTestResult(
        visible=make_command(visible),
        hidden=make_command(hidden, hidden=True),
        visible_passed=visible,
        hidden_passed=hidden,
        all_passed=visible and hidden,
        regression_detected=regression,
    )


def make_strategy_result(
    tmp_path: Path,
    *,
    visible: bool = True,
    hidden: bool = True,
    regression: bool = False,
    agent_success: bool = True,
    strategy_success: bool | None = None,
) -> StrategyBenchmarkResult:
    success = agent_success and visible and hidden and not regression
    if strategy_success is not None:
        success = strategy_success
    tool_calls = [
        ToolCallRecord(
            tool_name="list_files",
            arguments={},
            success=True,
            output="[]",
        ),
        ToolCallRecord(
            tool_name="read_file",
            arguments={"relative_path": "source.py"},
            success=agent_success,
            output="source" if agent_success else None,
            error=None if agent_success else "bad arguments",
        ),
        ToolCallRecord(
            tool_name="write_file",
            arguments={"relative_path": "source.py", "content": "fixed"},
            success=agent_success,
            output="null" if agent_success else None,
            error=None if agent_success else "not reached",
        ),
    ]
    agent_result = CodingAgentResult(
        task_id="easy-validation",
        agent_name="coding-agent",
        success=agent_success,
        final_answer="done" if agent_success else None,
        tool_calls=tool_calls,
        iterations=4,
        latency_ms=10,
        error=None if agent_success else "LLM error: 429 Too Many Requests",
    )
    failure_category = FailureCategory.NONE
    if regression:
        failure_category = FailureCategory.REGRESSION
    elif not visible:
        failure_category = FailureCategory.VISIBLE_TEST_FAILURE
    elif not hidden:
        failure_category = FailureCategory.HIDDEN_TEST_FAILURE
    elif not agent_success:
        failure_category = FailureCategory.AGENT_ERROR
    return StrategyBenchmarkResult(
        strategy_name="direct",
        task_id="easy-validation",
        success=success,
        agent_success=agent_success,
        agent_result=agent_result,
        test_result=make_test_result(
            visible=visible,
            hidden=hidden,
            regression=regression,
        ),
        metrics=CodingMetrics(
            task_success=success,
            regression_detected=regression,
            tool_calls=3,
            runtime_ms=12.5,
            files_changed=1,
            lines_added=2,
            lines_removed=1,
            patch_size=3,
            failure_category=failure_category,
        ),
        workspace_path=str(tmp_path / "kept-workspace"),
    )


def install_success_fakes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    baseline: CodingTestResult | None = None,
    strategy_result: StrategyBenchmarkResult | None = None,
    snapshots: list[dict[str, bytes]] | None = None,
) -> tuple[CodingTask, dict[str, Any]]:
    task = make_task(tmp_path)
    captured: dict[str, Any] = {}
    snapshots = snapshots or [
        {"source.py": b"broken = True\n"},
        {"source.py": b"broken = True\n"},
    ]
    snapshot_iterator = iter(snapshots)

    monkeypatch.setattr(validation, "check_docker", lambda image: (True, True))
    monkeypatch.setattr(
        validation.CodingTaskLoader,
        "load_directory",
        lambda path: [task],
    )
    monkeypatch.setattr(
        validation,
        "snapshot_repository",
        lambda path: next(snapshot_iterator),
    )
    monkeypatch.setattr(
        validation,
        "run_baseline",
        lambda loaded_task, image: baseline
        or make_test_result(visible=False, hidden=False),
    )

    def fake_run_selected_strategy(
        loaded_task: CodingTask,
        **kwargs: Any,
    ) -> StrategyBenchmarkResult:
        captured.update(kwargs)
        return strategy_result or make_strategy_result(tmp_path)

    monkeypatch.setattr(validation, "run_selected_strategy", fake_run_selected_strategy)
    return task, captured


def test_successful_validation_report_and_no_hidden_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, captured = install_success_fakes(monkeypatch, tmp_path)

    exit_code = validation.main(["--task", "easy-validation"])
    output = capsys.readouterr()

    assert exit_code == 0
    for expected in [
        "Task ID: easy-validation",
        "Difficulty: easy",
        "Provider: gemini",
        "Model: gemini-3.5-flash",
        "Strategy: direct",
        "Docker available: True",
        "Baseline visible passed: False",
        "Baseline hidden passed: False",
        "Agent success: True",
        "Tool call status: list_files:success, read_file:success, write_file:success",
        "Final iteration count: 4",
        "Post visible passed: True",
        "Post hidden passed: True",
        "Regression detected: False",
        "Tool calls: 3",
        "Runtime: 12.50 ms",
        "Files changed: 1",
        "Lines added: 2",
        "Lines removed: 1",
        "Patch size: 3",
        "Failure category: none",
        "Original fixture unchanged: True",
        "Validation success: True",
    ]:
        assert expected in output.out
    assert "HIDDEN STDOUT SECRET" not in output.out + output.err
    assert "HIDDEN STDERR SECRET" not in output.out + output.err
    assert "Kept workspace:" not in output.out
    assert captured["provider"] == "gemini"
    assert captured["max_iterations"] == 20


def test_openrouter_provider_is_forwarded_to_validation_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, captured = install_success_fakes(monkeypatch, tmp_path)

    exit_code = validation.main(
        [
            "--task",
            "easy-validation",
            "--provider",
            "openrouter",
            "--model",
            "provider/model",
        ]
    )

    assert exit_code == 0
    assert captured["provider"] == "openrouter"
    assert captured["model"] == "provider/model"
    assert "Provider: openrouter" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("docker_state", "expected_error"),
    [
        ((False, False), "Docker Desktop/Engine is not available"),
        ((True, False), validation.BUILD_COMMAND),
    ],
)
def test_docker_setup_failures_return_environment_error(
    docker_state: tuple[bool, bool],
    expected_error: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(validation, "check_docker", lambda image: docker_state)

    assert validation.main([]) == 2
    assert expected_error in capsys.readouterr().err


def test_missing_task_returns_environment_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(validation, "check_docker", lambda image: (True, True))
    monkeypatch.setattr(validation.CodingTaskLoader, "load_directory", lambda path: [])

    assert validation.main(["--task", "missing"]) == 2
    assert "coding task not found: missing" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("baseline", "strategy_options"),
    [
        (make_test_result(visible=True, hidden=True), {}),
        (make_test_result(visible=False, hidden=False), {"visible": False}),
        (make_test_result(visible=False, hidden=False), {"hidden": False}),
        (make_test_result(visible=False, hidden=False), {"regression": True}),
        (make_test_result(visible=False, hidden=False), {"agent_success": False}),
        (make_test_result(visible=False, hidden=False), {"strategy_success": False}),
    ],
)
def test_validation_failures_return_one(
    baseline: CodingTestResult,
    strategy_options: dict[str, bool],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_success_fakes(
        monkeypatch,
        tmp_path,
        baseline=baseline,
        strategy_result=make_strategy_result(tmp_path, **strategy_options),
    )

    assert validation.main(["--task", "easy-validation"]) == 1
    assert "Validation success: False" in capsys.readouterr().out


def test_original_fixture_mutation_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_success_fakes(
        monkeypatch,
        tmp_path,
        snapshots=[{"source.py": b"before"}, {"source.py": b"after"}],
    )

    assert validation.main(["--task", "easy-validation"]) == 1
    output = capsys.readouterr().out
    assert "Original fixture unchanged: False" in output
    assert "Validation success: False" in output


def test_failed_agent_diagnostics_are_concise_and_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_success_fakes(
        monkeypatch,
        tmp_path,
        strategy_result=make_strategy_result(tmp_path, agent_success=False),
    )

    assert validation.main(["--task", "easy-validation"]) == 1
    output = capsys.readouterr().out
    assert "Agent error: LLM error: 429 Too Many Requests" in output
    assert (
        "Tool call status: list_files:success, read_file:failed, write_file:failed"
        in output
    )
    assert "Final iteration count: 4" in output
    assert "source.py" not in output
    assert "fixed" not in output


def test_keep_workspace_is_forwarded_and_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, captured = install_success_fakes(monkeypatch, tmp_path)

    assert validation.main(
        ["--task", "easy-validation", "--keep-workspace"]
    ) == 0
    output = capsys.readouterr().out

    assert captured["keep_workspace"] is True
    assert f"Kept workspace: {tmp_path / 'kept-workspace'}" in output


def test_invalid_iteration_count_returns_setup_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called = False

    def fake_check_docker(image: str) -> tuple[bool, bool]:
        nonlocal called
        called = True
        return True, True

    monkeypatch.setattr(validation, "check_docker", fake_check_docker)

    assert validation.main(["--max-iterations", "0"]) == 2
    assert called is False
    assert "max-iterations must be greater than zero" in capsys.readouterr().err


def test_report_function_does_not_print_hidden_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task = make_task(tmp_path)
    args = Namespace(
        provider="gemini",
        model="gemini-3.5-flash",
        strategy="direct",
        keep_workspace=False,
    )
    validation._print_report(
        args,
        task,
        make_test_result(visible=False, hidden=False),
        make_strategy_result(tmp_path),
        True,
        True,
    )

    output = capsys.readouterr()
    assert "HIDDEN STDOUT SECRET" not in output.out + output.err
    assert "HIDDEN STDERR SECRET" not in output.out + output.err
