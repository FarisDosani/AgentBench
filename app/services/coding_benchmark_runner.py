import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from app.models.coding_agent import CodingAgentResult
from app.models.coding_benchmark_run import (
    CodingBenchmarkRunResult,
    StrategyBenchmarkResult,
)
from app.models.coding_metrics import FailureCategory
from app.models.coding_task import CodingTask
from app.models.test_result import CodingTestResult, TestCommandResult
from app.services.coding_metrics import CodingMetricsCollector
from app.services.repository_workspace import RepositoryWorkspace


class Strategy(Protocol):
    def run(self, task: CodingTask) -> object: ...


StrategyFactory = Callable[[CodingTask, Path], Strategy]


FAILURE_SEVERITY = {
    FailureCategory.NONE: 0,
    FailureCategory.REVIEWER_REJECTION: 1,
    FailureCategory.HIDDEN_TEST_FAILURE: 2,
    FailureCategory.VISIBLE_TEST_FAILURE: 3,
    FailureCategory.REGRESSION: 4,
    FailureCategory.TOOL_ERROR: 5,
    FailureCategory.AGENT_ERROR: 6,
    FailureCategory.MALFORMED_RESPONSE: 6,
    FailureCategory.MAX_ITERATIONS: 6,
    FailureCategory.TIMEOUT: 7,
    FailureCategory.UNKNOWN: 8,
}


class CodingBenchmarkRunner:
    def __init__(
        self,
        direct_factory: StrategyFactory,
        planner_executor_factory: StrategyFactory,
        reviewer_factory: StrategyFactory,
        metrics_collector: CodingMetricsCollector,
        temp_root: str | Path | None = None,
        keep_workspaces: bool = False,
    ) -> None:
        self.factories = {
            "direct": direct_factory,
            "planner_executor": planner_executor_factory,
            "reviewer": reviewer_factory,
        }
        self.metrics_collector = metrics_collector
        self.temp_root = Path(temp_root).resolve() if temp_root is not None else None
        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True)
        self.keep_workspaces = keep_workspaces

    def run_task(
        self,
        task: CodingTask,
        strategies: list[str] | None = None,
    ) -> CodingBenchmarkRunResult:
        requested = list(self.factories) if strategies is None else list(strategies)
        unknown = [name for name in requested if name not in self.factories]
        if unknown:
            raise ValueError(f"Unknown coding strategy: {unknown[0]}")

        strategy_results = [
            self._run_strategy(task, strategy_name) for strategy_name in requested
        ]
        best_strategy = None
        if strategy_results:
            best_strategy = min(strategy_results, key=self._ranking_key).strategy_name

        return CodingBenchmarkRunResult(
            task_id=task.id,
            difficulty=task.difficulty,
            strategy_results=strategy_results,
            best_strategy=best_strategy,
        )

    def _run_strategy(
        self,
        original_task: CodingTask,
        strategy_name: str,
    ) -> StrategyBenchmarkResult:
        strategy_root = Path(
            tempfile.mkdtemp(
                prefix=f"agentbench-{strategy_name}-",
                dir=self.temp_root,
            )
        ).resolve()
        workspace_path = strategy_root / "repository"
        source_path = Path(original_task.repository_path).resolve()

        try:
            shutil.copytree(source_path, workspace_path, ignore=self._ignore_symlinks)
            copied_task = original_task.model_copy(
                update={"repository_path": str(workspace_path)}
            )
            before = self._snapshot(workspace_path)
            started_at = time.perf_counter()

            try:
                strategy = self.factories[strategy_name](copied_task, workspace_path)
                outcome = strategy.run(copied_task)
                test_result = outcome.test_result
                agent_result = self._combined_agent_result(outcome, copied_task)
                success = bool(outcome.success)
                error = None
            except Exception as exception:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                error = f"{type(exception).__name__}: {exception}"
                agent_result = self._failed_agent_result(copied_task, elapsed_ms, error)
                test_result = self._failed_test_result(error)
                success = False

            after = self._snapshot(workspace_path)
            metrics = self.metrics_collector.collect(
                agent_result,
                test_result,
                before,
                after,
                task_success=success,
            )
            return StrategyBenchmarkResult(
                strategy_name=strategy_name,
                task_id=original_task.id,
                success=success,
                test_result=test_result,
                metrics=metrics,
                workspace_path=str(workspace_path),
                error=error,
            )
        finally:
            if not self.keep_workspaces:
                shutil.rmtree(strategy_root, ignore_errors=True)

    @staticmethod
    def _ignore_symlinks(directory: str, names: list[str]) -> set[str]:
        directory_path = Path(directory)
        return {name for name in names if (directory_path / name).is_symlink()}

    @staticmethod
    def _snapshot(workspace_path: Path) -> dict[str, str]:
        workspace = RepositoryWorkspace(workspace_path)
        snapshot: dict[str, str] = {}
        for relative_path in workspace.list_files():
            try:
                snapshot[relative_path] = workspace.read_file(relative_path)
            except (UnicodeDecodeError, OSError):
                continue
        return snapshot

    @staticmethod
    def _combined_agent_result(outcome: object, task: CodingTask) -> CodingAgentResult:
        singular = getattr(outcome, "agent_result", None)
        if isinstance(singular, CodingAgentResult):
            return singular

        multiple = getattr(outcome, "agent_results", None)
        if isinstance(multiple, list) and multiple:
            results = [result for result in multiple if isinstance(result, CodingAgentResult)]
            if results:
                return CodingAgentResult(
                    task_id=task.id,
                    agent_name=results[0].agent_name,
                    success=all(result.success for result in results),
                    final_answer=results[-1].final_answer,
                    tool_calls=[
                        call for result in results for call in result.tool_calls
                    ],
                    iterations=sum(result.iterations for result in results),
                    latency_ms=sum(result.latency_ms for result in results),
                    error=next(
                        (result.error for result in results if result.error), None
                    ),
                )
        raise ValueError("Strategy result does not contain coding agent results")

    @staticmethod
    def _failed_agent_result(
        task: CodingTask,
        latency_ms: float,
        error: str,
    ) -> CodingAgentResult:
        return CodingAgentResult(
            task_id=task.id,
            agent_name="strategy-runner",
            success=False,
            final_answer=None,
            tool_calls=[],
            iterations=0,
            latency_ms=latency_ms,
            error=error,
        )

    @staticmethod
    def _failed_test_result(error: str) -> CodingTestResult:
        command_result = TestCommandResult(
            command="strategy execution",
            exit_code=-1,
            stdout="",
            stderr=error,
            passed=False,
            timed_out=False,
            duration_ms=0,
        )
        return CodingTestResult(
            visible=command_result,
            hidden=None,
            visible_passed=False,
            hidden_passed=None,
            all_passed=False,
            regression_detected=False,
        )

    @staticmethod
    def _ranking_key(result: StrategyBenchmarkResult) -> tuple[object, ...]:
        return (
            not result.success,
            FAILURE_SEVERITY[result.metrics.failure_category],
            result.metrics.runtime_ms,
            result.metrics.tool_calls,
            result.strategy_name,
        )
