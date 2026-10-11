from app.models.coding_task import CodingTask
from app.models.strategy_result import StrategyResult
from app.services.coding_agent_runner import CodingAgentRunner
from app.services.coding_test_runner import CodingTestRunner


class DirectStrategy:
    strategy_name = "direct"

    def __init__(
        self,
        agent_runner: CodingAgentRunner,
        test_runner: CodingTestRunner,
    ) -> None:
        self.agent_runner = agent_runner
        self.test_runner = test_runner

    def run(self, task: CodingTask) -> StrategyResult:
        baseline = self.test_runner.run_baseline(task)
        agent_result = self.agent_runner.run(task)
        test_result = self.test_runner.run_after_changes(task, baseline)
        success = (
            agent_result.success
            and test_result.all_passed
            and not test_result.regression_detected
        )
        return StrategyResult(
            strategy_name=self.strategy_name,
            task_id=task.id,
            agent_result=agent_result,
            test_result=test_result,
            success=success,
        )
