import pytest
from pydantic import ValidationError

from app.models.evaluation import EvaluationResult
from app.models.result import AgentRunResult
from app.models.task import BenchmarkTask
from app.services.evaluator import ExactMatchEvaluator


def make_task(expected_output: str | None = "Expected") -> BenchmarkTask:
    return BenchmarkTask(
        id="task-1",
        name="Evaluation task",
        description="A task used to test evaluation.",
        input="Provide the expected output.",
        expected_output=expected_output,
    )


def make_result(
    output: str | None = "Expected",
    *,
    success: bool = True,
    task_id: str = "task-1",
    error: str | None = None,
) -> AgentRunResult:
    return AgentRunResult(
        agent_name="test-agent",
        task_id=task_id,
        output=output,
        success=success,
        latency_ms=1.0,
        error=error,
    )


def test_exact_match_passes() -> None:
    evaluation = ExactMatchEvaluator().evaluate(make_task(), make_result())

    assert evaluation.score == 1.0
    assert evaluation.passed is True
    assert evaluation.reason is None
    assert evaluation.task_id == "task-1"
    assert evaluation.agent_name == "test-agent"


def test_surrounding_whitespace_is_ignored() -> None:
    evaluation = ExactMatchEvaluator().evaluate(
        make_task("  Expected\n"), make_result("\tExpected  ")
    )

    assert evaluation.passed is True
    assert evaluation.score == 1.0


def test_case_difference_fails() -> None:
    evaluation = ExactMatchEvaluator().evaluate(make_task("Expected"), make_result("expected"))

    assert evaluation.passed is False
    assert evaluation.score == 0.0
    assert evaluation.reason is not None


def test_incorrect_output_fails() -> None:
    evaluation = ExactMatchEvaluator().evaluate(make_task(), make_result("Incorrect"))

    assert evaluation.passed is False
    assert evaluation.score == 0.0
    assert evaluation.reason == "Output did not match expected output"


def test_failed_run_scores_zero() -> None:
    evaluation = ExactMatchEvaluator().evaluate(
        make_task(), make_result(None, success=False, error="executor failed")
    )

    assert evaluation.passed is False
    assert evaluation.score == 0.0
    assert evaluation.reason == "Execution failed: executor failed"


def test_missing_expected_output_fails_cleanly() -> None:
    evaluation = ExactMatchEvaluator().evaluate(make_task(None), make_result())

    assert evaluation.passed is False
    assert evaluation.score == 0.0
    assert evaluation.reason == "Expected output is unavailable"


def test_mismatched_task_ids_raise_value_error() -> None:
    with pytest.raises(ValueError):
        ExactMatchEvaluator().evaluate(make_task(), make_result(task_id="other-task"))


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_evaluation_result_rejects_out_of_range_score(score: float) -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(
            task_id="task-1",
            agent_name="test-agent",
            score=score,
            passed=False,
        )
