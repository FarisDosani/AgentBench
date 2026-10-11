from collections.abc import Callable

from app.models.coding_task import CodingTask
from app.models.plan import AgentPlan, PlannerExecutorResult
from app.services.coding_agent_runner import CodingAgentRunner
from app.services.coding_test_runner import CodingTestRunner


Planner = Callable[[CodingTask], AgentPlan]


class PlannerExecutorStrategy:
    strategy_name = "planner_executor"

    def __init__(
        self,
        planner: Planner,
        agent_runner: CodingAgentRunner,
        test_runner: CodingTestRunner,
    ) -> None:
        self.planner = planner
        self.agent_runner = agent_runner
        self.test_runner = test_runner

    def run(self, task: CodingTask) -> PlannerExecutorResult:
        baseline = self.test_runner.run_baseline(task)
        plan = self.planner(task)
        agent_results = []

        for step in plan.steps:
            result = self.agent_runner.run(
                task,
                extra_context=f"Plan step {step.id}: {step.description}",
            )
            agent_results.append(result)
            if not result.success:
                break
            step.completed = True

        test_result = self.test_runner.run_after_changes(task, baseline)
        success = (
            len(agent_results) == len(plan.steps)
            and all(result.success for result in agent_results)
            and test_result.all_passed
            and not test_result.regression_detected
        )
        return PlannerExecutorResult(
            strategy_name=self.strategy_name,
            task_id=task.id,
            plan=plan,
            agent_results=agent_results,
            test_result=test_result,
            success=success,
        )
