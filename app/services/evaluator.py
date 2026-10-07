from app.models.evaluation import EvaluationResult
from app.models.result import AgentRunResult
from app.models.task import BenchmarkTask


class ExactMatchEvaluator:
    def evaluate(
        self,
        task: BenchmarkTask,
        result: AgentRunResult,
    ) -> EvaluationResult:
        if result.task_id != task.id:
            raise ValueError(
                f"Result task ID {result.task_id!r} does not match task ID {task.id!r}"
            )

        if not result.success:
            reason = "Execution failed"
            if result.error:
                reason = f"{reason}: {result.error}"
            return EvaluationResult(
                task_id=task.id,
                agent_name=result.agent_name,
                score=0.0,
                passed=False,
                reason=reason,
            )

        if task.expected_output is None:
            return EvaluationResult(
                task_id=task.id,
                agent_name=result.agent_name,
                score=0.0,
                passed=False,
                reason="Expected output is unavailable",
            )

        if result.output is not None and result.output.strip() == task.expected_output.strip():
            return EvaluationResult(
                task_id=task.id,
                agent_name=result.agent_name,
                score=1.0,
                passed=True,
                reason=None,
            )

        return EvaluationResult(
            task_id=task.id,
            agent_name=result.agent_name,
            score=0.0,
            passed=False,
            reason="Output did not match expected output",
        )
