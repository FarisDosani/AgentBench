from typing import Protocol

from app.models.agent import AgentConfig
from app.models.benchmark import BenchmarkRunResult, BenchmarkTaskResult
from app.models.evaluation import EvaluationResult
from app.models.result import AgentRunResult
from app.models.task import BenchmarkTask
from app.services.runner import AgentRunner


class Evaluator(Protocol):
    def evaluate(
        self,
        task: BenchmarkTask,
        result: AgentRunResult,
    ) -> EvaluationResult: ...


class BenchmarkRunner:
    def __init__(self, runner: AgentRunner, evaluator: Evaluator) -> None:
        self.runner = runner
        self.evaluator = evaluator

    def run(
        self,
        agent: AgentConfig,
        tasks: list[BenchmarkTask],
    ) -> BenchmarkRunResult:
        results: list[BenchmarkTaskResult] = []

        for task in tasks:
            run_result = self.runner.run(agent, task)
            evaluation = self.evaluator.evaluate(task, run_result)
            results.append(
                BenchmarkTaskResult(
                    run_result=run_result,
                    evaluation=evaluation,
                )
            )

        total_tasks = len(results)
        passed_tasks = sum(result.evaluation.passed for result in results)

        if total_tasks:
            average_score = (
                sum(result.evaluation.score for result in results) / total_tasks
            )
            average_latency_ms = (
                sum(result.run_result.latency_ms for result in results) / total_tasks
            )
        else:
            average_score = 0.0
            average_latency_ms = 0.0

        return BenchmarkRunResult(
            agent_name=agent.name,
            total_tasks=total_tasks,
            passed_tasks=passed_tasks,
            failed_tasks=total_tasks - passed_tasks,
            average_score=average_score,
            average_latency_ms=average_latency_ms,
            results=results,
        )
