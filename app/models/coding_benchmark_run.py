from typing import Annotated

from pydantic import BaseModel, StringConstraints, model_validator

from app.models.coding_metrics import CodingMetrics
from app.models.coding_task import TaskDifficulty
from app.models.test_result import CodingTestResult


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrategyBenchmarkResult(BaseModel):
    strategy_name: NonEmptyStr
    task_id: NonEmptyStr
    success: bool
    test_result: CodingTestResult
    metrics: CodingMetrics
    workspace_path: str
    error: str | None = None


class CodingBenchmarkRunResult(BaseModel):
    task_id: NonEmptyStr
    difficulty: TaskDifficulty
    strategy_results: list[StrategyBenchmarkResult]
    best_strategy: str | None

    @model_validator(mode="after")
    def validate_best_strategy(self) -> "CodingBenchmarkRunResult":
        strategy_names = {result.strategy_name for result in self.strategy_results}
        if self.best_strategy is not None and self.best_strategy not in strategy_names:
            raise ValueError("best_strategy must match a returned strategy")
        return self
