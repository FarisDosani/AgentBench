from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.coding_agent import CodingAgentResult, ToolCallRecord
from app.models.coding_benchmark_run import CodingBenchmarkRunResult
from app.models.coding_task import CodingTask, TaskDifficulty
from app.models.strategy_result import StrategyResult
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult
from app.services.coding_benchmark_runner import CodingBenchmarkRunner
from app.services.coding_metrics import CodingMetricsCollector


def make_task(tmp_path: Path) -> CodingTask:
    repository = tmp_path / "fixture"
    repository.mkdir()
    (repository / "source.py").write_text("original\n", encoding="utf-8")
    return CodingTask(
        id="coding-task",
        name="Coding benchmark",
        description="Modify the source safely.",
        repository_path=str(repository),
        difficulty="hard",
        visible_test_command="pytest -q tests",
        hidden_test_command="pytest -q hidden_tests",
        allowed_tools=["list_files", "read_file", "search_repo", "write_file"],
    )


def make_test_result(passed: bool = True, duration_ms: float = 0) -> CodingTestResult:
    command = CommandResult(
        command="pytest -q tests",
        exit_code=0 if passed else 1,
        stdout="visible only",
        stderr="",
        passed=passed,
        timed_out=False,
        duration_ms=duration_ms,
    )
    return CodingTestResult(
        visible=command,
        hidden=None,
        visible_passed=passed,
        hidden_passed=None,
        all_passed=passed,
        regression_detected=False,
    )


def make_outcome(
    strategy_name: str,
    *,
    success: bool = True,
    latency_ms: float = 1,
    tool_calls: int = 1,
) -> StrategyResult:
    calls = [
        ToolCallRecord(
            tool_name="write_file",
            arguments={"relative_path": "changed.py"},
            success=True,
            output="null",
        )
        for _ in range(tool_calls)
    ]
    agent = CodingAgentResult(
        task_id="coding-task",
        agent_name="agent",
        success=success,
        final_answer="done" if success else None,
        tool_calls=calls,
        iterations=1,
        latency_ms=latency_ms,
        error=None if success else "agent failed",
    )
    return StrategyResult(
        strategy_name=strategy_name,
        task_id="coding-task",
        agent_result=agent,
        test_result=make_test_result(success),
        success=success,
    )


class FakeStrategy:
    def __init__(
        self,
        workspace: Path,
        outcome: StrategyResult,
        marker: str,
        seen_initial_files: list[set[str]],
    ) -> None:
        self.workspace = workspace
        self.outcome = outcome
        self.marker = marker
        self.seen_initial_files = seen_initial_files

    def run(self, task: CodingTask) -> StrategyResult:
        assert Path(task.repository_path) == self.workspace
        self.seen_initial_files.append(
            {path.name for path in self.workspace.iterdir() if path.is_file()}
        )
        (self.workspace / f"{self.marker}.py").write_text(
            f"{self.marker}\n", encoding="utf-8"
        )
        return self.outcome


def make_factory(
    name: str,
    outcome: StrategyResult,
    received: list[tuple[str, CodingTask, Path]],
    seen_initial_files: list[set[str]],
):
    def factory(task: CodingTask, workspace: Path) -> FakeStrategy:
        received.append((name, task, workspace))
        return FakeStrategy(workspace, outcome, name, seen_initial_files)

    return factory


def make_runner(
    temp_root: Path,
    outcomes: dict[str, StrategyResult],
    received: list[tuple[str, CodingTask, Path]] | None = None,
    seen_initial_files: list[set[str]] | None = None,
) -> CodingBenchmarkRunner:
    received = received if received is not None else []
    seen_initial_files = seen_initial_files if seen_initial_files is not None else []
    return CodingBenchmarkRunner(
        make_factory("direct", outcomes["direct"], received, seen_initial_files),
        make_factory(
            "planner_executor", outcomes["planner_executor"], received, seen_initial_files
        ),
        make_factory("reviewer", outcomes["reviewer"], received, seen_initial_files),
        CodingMetricsCollector(),
        temp_root=temp_root,
    )


def default_outcomes() -> dict[str, StrategyResult]:
    return {
        name: make_outcome(name)
        for name in ["direct", "planner_executor", "reviewer"]
    }


def test_all_strategies_are_isolated_ordered_and_cleaned(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    original_dump = task.model_dump()
    received: list[tuple[str, CodingTask, Path]] = []
    seen: list[set[str]] = []
    result = make_runner(tmp_path / "temp", default_outcomes(), received, seen).run_task(task)

    assert [item.strategy_name for item in result.strategy_results] == [
        "direct",
        "planner_executor",
        "reviewer",
    ]
    workspace_paths = [path for _, _, path in received]
    assert len(set(workspace_paths)) == 3
    assert seen == [{"source.py"}, {"source.py"}, {"source.py"}]
    assert all(not path.exists() for path in workspace_paths)
    assert (Path(task.repository_path) / "source.py").read_text(encoding="utf-8") == "original\n"
    assert list(Path(task.repository_path).glob("direct.py")) == []
    assert task.model_dump() == original_dump
    assert result.difficulty is TaskDifficulty.HARD
    assert all(item.metrics.files_changed == 1 for item in result.strategy_results)
    assert all(item.metrics.patch_size == 1 for item in result.strategy_results)


def test_requested_subset_order_unknown_and_empty(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    runner = make_runner(tmp_path / "temp", default_outcomes())

    subset = runner.run_task(task, ["reviewer", "direct"])
    assert [item.strategy_name for item in subset.strategy_results] == [
        "reviewer",
        "direct",
    ]
    assert runner.run_task(task, []).strategy_results == []
    assert runner.run_task(task, []).best_strategy is None
    with pytest.raises(ValueError, match="Unknown coding strategy"):
        runner.run_task(task, ["unknown"])


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        (
            {
                "direct": make_outcome("direct", success=False, latency_ms=1),
                "planner_executor": make_outcome("planner_executor", latency_ms=50),
                "reviewer": make_outcome("reviewer", latency_ms=60),
            },
            "planner_executor",
        ),
        (
            {
                "direct": make_outcome("direct", latency_ms=20),
                "planner_executor": make_outcome("planner_executor", latency_ms=10),
                "reviewer": make_outcome("reviewer", latency_ms=30),
            },
            "planner_executor",
        ),
        (
            {
                "direct": make_outcome("direct", latency_ms=10, tool_calls=2),
                "planner_executor": make_outcome(
                    "planner_executor", latency_ms=10, tool_calls=1
                ),
                "reviewer": make_outcome("reviewer", latency_ms=20),
            },
            "planner_executor",
        ),
        (
            {
                "direct": make_outcome("direct", latency_ms=10, tool_calls=1),
                "planner_executor": make_outcome(
                    "planner_executor", latency_ms=10, tool_calls=1
                ),
                "reviewer": make_outcome("reviewer", latency_ms=10, tool_calls=1),
            },
            "direct",
        ),
    ],
)
def test_best_strategy_tie_breaking(
    tmp_path: Path,
    outcomes: dict[str, StrategyResult],
    expected: str,
) -> None:
    result = make_runner(tmp_path / "temp", outcomes).run_task(make_task(tmp_path))
    assert result.best_strategy == expected


def test_strategy_exception_does_not_stop_remaining_strategies(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    outcomes = default_outcomes()
    received: list[str] = []

    def exploding_factory(task: CodingTask, workspace: Path):
        received.append("direct")
        raise RuntimeError("exploded")

    def factory(name: str):
        def create(task: CodingTask, workspace: Path) -> FakeStrategy:
            received.append(name)
            return FakeStrategy(workspace, outcomes[name], name, [])

        return create

    runner = CodingBenchmarkRunner(
        exploding_factory,
        factory("planner_executor"),
        factory("reviewer"),
        CodingMetricsCollector(),
        temp_root=tmp_path / "temp",
    )
    result = runner.run_task(task)

    assert received == ["direct", "planner_executor", "reviewer"]
    assert result.strategy_results[0].success is False
    assert result.strategy_results[0].error == "RuntimeError: exploded"
    assert result.strategy_results[0].metrics.failure_category.value == "agent_error"
    assert result.strategy_results[1].success is True
    assert result.strategy_results[2].success is True


def test_best_strategy_validation_rejects_unknown_name(tmp_path: Path) -> None:
    valid = make_runner(tmp_path / "temp", default_outcomes()).run_task(
        make_task(tmp_path), ["direct"]
    )
    with pytest.raises(ValidationError):
        CodingBenchmarkRunResult(
            task_id=valid.task_id,
            difficulty=valid.difficulty,
            strategy_results=valid.strategy_results,
            best_strategy="missing",
        )
