from typing import Protocol

from app.models.coding_task import CodingTask
from app.models.strategy_result import StrategyResult


class CodingStrategy(Protocol):
    strategy_name: str

    def run(self, task: CodingTask) -> StrategyResult: ...
