from typing import Any

import pytest
from pydantic import ValidationError

from app.models.benchmark import BenchmarkRunResult
from app.models.comparison import AgentComparisonSummary
from app.services.comparison_service import ComparisonService


def make_run(
    agent_name: str,
    average_score: float,
    average_latency_ms: float,
    passed_tasks: int,
    total_tasks: int = 3,
) -> BenchmarkRunResult:
    return BenchmarkRunResult(
        agent_name=agent_name,
        total_tasks=total_tasks,
        passed_tasks=passed_tasks,
        failed_tasks=total_tasks - passed_tasks,
        average_score=average_score,
        average_latency_ms=average_latency_ms,
        results=[],
    )


def test_multiple_runs_are_ranked_deterministically_and_reported() -> None:
    runs = [
        make_run("slow-high", 1.0, 120.5, 3),
        make_run("zeta-fast", 1.0, 90.2, 3),
        make_run("alpha-fast", 1.0, 90.2, 3),
        make_run("lower-score", 2 / 3, 10.0, 2),
    ]
    original_order = list(runs)

    comparison = ComparisonService().compare(runs)

    assert [summary.agent_name for summary in comparison.summaries] == [
        "alpha-fast",
        "zeta-fast",
        "slow-high",
        "lower-score",
    ]
    assert [summary.rank for summary in comparison.summaries] == [1, 2, 3, 4]
    assert comparison.best_agent == "alpha-fast"
    assert runs == original_order

    for agent_name in ["alpha-fast", "zeta-fast", "slow-high", "lower-score"]:
        assert agent_name in comparison.report
    assert "Score: 1.00" in comparison.report
    assert "Score: 0.67" in comparison.report
    assert "Passed: 3/3" in comparison.report
    assert "Passed: 2/3" in comparison.report


def test_empty_run_list_is_handled() -> None:
    comparison = ComparisonService().compare([])

    assert comparison.summaries == []
    assert comparison.best_agent is None
    assert "no benchmark runs available" in comparison.report.lower()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rank", 0),
        ("agent_name", "   "),
        ("average_score", -0.1),
        ("average_score", 1.1),
        ("average_latency_ms", -0.1),
        ("passed_tasks", -1),
        ("failed_tasks", -1),
        ("total_tasks", -1),
    ],
)
def test_invalid_comparison_summary_values_are_rejected(
    field: str,
    value: Any,
) -> None:
    values: dict[str, Any] = {
        "rank": 1,
        "agent_name": "agent",
        "average_score": 1.0,
        "average_latency_ms": 10.0,
        "passed_tasks": 1,
        "failed_tasks": 0,
        "total_tasks": 1,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        AgentComparisonSummary(**values)
