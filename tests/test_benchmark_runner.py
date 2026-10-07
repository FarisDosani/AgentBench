import pytest

from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask
from app.services.benchmark_runner import BenchmarkRunner
from app.services.evaluator import ExactMatchEvaluator
from app.services.runner import AgentRunner


def make_agent() -> AgentConfig:
    return AgentConfig(name="benchmark-agent", model="test-model")


def make_task(task_id: str, expected_output: str) -> BenchmarkTask:
    return BenchmarkTask(
        id=task_id,
        name=f"Task {task_id}",
        description="A benchmark task.",
        input=task_id,
        expected_output=expected_output,
    )


def test_multiple_tasks_are_run_evaluated_and_aggregated_in_order() -> None:
    tasks = [
        make_task("first", "correct"),
        make_task("second", "expected"),
        make_task("third", "unused"),
    ]

    def executor(agent: AgentConfig, task: BenchmarkTask) -> str:
        if task.id == "third":
            raise RuntimeError("executor failed")
        return {"first": "correct", "second": "incorrect"}[task.id]

    result = BenchmarkRunner(
        AgentRunner(executor),
        ExactMatchEvaluator(),
    ).run(make_agent(), tasks)

    assert result.agent_name == "benchmark-agent"
    assert result.total_tasks == 3
    assert [item.run_result.task_id for item in result.results] == [
        "first",
        "second",
        "third",
    ]
    assert result.passed_tasks == 1
    assert result.failed_tasks == 2
    assert result.average_score == pytest.approx(1 / 3)
    assert result.average_latency_ms >= 0
    assert result.results[2].run_result.success is False
    assert result.results[2].evaluation.passed is False
    assert result.results[2].evaluation.score == 0.0


def test_empty_task_list_is_handled() -> None:
    def executor(agent: AgentConfig, task: BenchmarkTask) -> str:
        raise AssertionError("Executor must not be called")

    result = BenchmarkRunner(
        AgentRunner(executor),
        ExactMatchEvaluator(),
    ).run(make_agent(), [])

    assert result.agent_name == "benchmark-agent"
    assert result.total_tasks == 0
    assert result.passed_tasks == 0
    assert result.failed_tasks == 0
    assert result.average_score == 0.0
    assert result.average_latency_ms == 0.0
    assert result.results == []
