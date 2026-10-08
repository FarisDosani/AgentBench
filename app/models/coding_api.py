from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models.coding_benchmark_run import CodingBenchmarkRunResult
from app.models.coding_metrics import CodingMetrics
from app.models.coding_task import CodingTask, TaskDifficulty


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
StrategyName = Literal["direct", "planner_executor", "reviewer"]


class CodingTaskSummary(BaseModel):
    id: str
    name: str
    description: str
    difficulty: TaskDifficulty
    allowed_tools: list[str]
    timeout_seconds: int
    expected_files_changed: list[str]
    metadata: dict[str, str]

    @classmethod
    def from_task(cls, task: CodingTask) -> "CodingTaskSummary":
        return cls(**task.model_dump(include=set(cls.model_fields)))


class CodingBenchmarkRequest(BaseModel):
    task_id: NonEmptyStr
    provider: Literal["gemini", "omniroute"] = "gemini"
    model: NonEmptyStr
    strategies: list[StrategyName] | None = None
    max_iterations: Annotated[int, Field(gt=0)] = 20
    keep_workspaces: bool = False


class SafeCodingTestSummary(BaseModel):
    visible_passed: bool
    hidden_passed: bool | None
    all_passed: bool
    regression_detected: bool


class SafeStrategyBenchmarkResult(BaseModel):
    strategy_name: str
    task_id: str
    success: bool
    test_summary: SafeCodingTestSummary
    metrics: CodingMetrics


class SafeCodingBenchmarkResponse(BaseModel):
    task_id: str
    difficulty: TaskDifficulty
    strategy_results: list[SafeStrategyBenchmarkResult]
    best_strategy: str | None

    @classmethod
    def from_result(
        cls,
        result: CodingBenchmarkRunResult,
    ) -> "SafeCodingBenchmarkResponse":
        return cls(
            task_id=result.task_id,
            difficulty=result.difficulty,
            strategy_results=[
                SafeStrategyBenchmarkResult(
                    strategy_name=item.strategy_name,
                    task_id=item.task_id,
                    success=item.success,
                    test_summary=SafeCodingTestSummary(
                        visible_passed=item.test_result.visible_passed,
                        hidden_passed=item.test_result.hidden_passed,
                        all_passed=item.test_result.all_passed,
                        regression_detected=item.test_result.regression_detected,
                    ),
                    metrics=item.metrics,
                )
                for item in result.strategy_results
            ],
            best_strategy=result.best_strategy,
        )
