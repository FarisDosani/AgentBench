import pytest
from pydantic import ValidationError

from app.models.coding_agent import CodingAgentResult, ToolCallRecord
from app.models.coding_metrics import CodingMetrics, FailureCategory
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult
from app.services.coding_metrics import CodingMetricsCollector


def make_agent(
    *,
    success: bool = True,
    error: str | None = None,
    tool_success: bool = True,
) -> CodingAgentResult:
    return CodingAgentResult(
        task_id="task-1",
        agent_name="agent",
        success=success,
        final_answer="done" if success else None,
        tool_calls=[
            ToolCallRecord(
                tool_name="read_file",
                arguments={"relative_path": "a.py"},
                success=tool_success,
                output="x" if tool_success else None,
                error=None if tool_success else "tool failed",
            )
        ],
        iterations=1,
        latency_ms=5,
        error=error,
    )


def make_tests(
    *,
    visible: bool = True,
    hidden: bool | None = None,
    regression: bool = False,
    timed_out: bool = False,
) -> CodingTestResult:
    visible_result = CommandResult(
        command="pytest",
        exit_code=0 if visible else 1,
        stdout="",
        stderr="",
        passed=visible and not timed_out,
        timed_out=timed_out,
        duration_ms=3,
    )
    hidden_result = None
    if hidden is not None:
        hidden_result = CommandResult(
            command="pytest hidden",
            exit_code=0 if hidden else 1,
            stdout="",
            stderr="",
            passed=hidden,
            timed_out=False,
            duration_ms=2,
        )
    return CodingTestResult(
        visible=visible_result,
        hidden=hidden_result,
        visible_passed=visible_result.passed,
        hidden_passed=hidden,
        all_passed=visible_result.passed and hidden is not False,
        regression_detected=regression,
    )


def test_success_metrics_patch_runtime_tools_and_optional_usage() -> None:
    metrics = CodingMetricsCollector().collect(
        make_agent(),
        make_tests(hidden=True),
        {"a.py": "one\ntwo", "same.py": "same"},
        {"a.py": "one\nthree", "same.py": "same", "new.py": "new"},
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost_usd=0.01,
    )

    assert metrics.task_success is True
    assert metrics.failure_category is FailureCategory.NONE
    assert metrics.tool_calls == 1
    assert metrics.runtime_ms == 10
    assert metrics.files_changed == 2
    assert metrics.lines_added == 2
    assert metrics.lines_removed == 1
    assert metrics.patch_size == 3
    assert metrics.prompt_tokens == 10
    assert metrics.completion_tokens == 5
    assert metrics.total_tokens == 15
    assert metrics.estimated_cost_usd == 0.01


def test_no_change_and_missing_usage_remain_zero_or_none() -> None:
    metrics = CodingMetricsCollector().collect(
        make_agent(), make_tests(), {"a": "same"}, {"a": "same"}
    )
    assert metrics.files_changed == 0
    assert metrics.lines_added == 0
    assert metrics.lines_removed == 0
    assert metrics.patch_size == 0
    assert metrics.prompt_tokens is None
    assert metrics.completion_tokens is None
    assert metrics.total_tokens is None
    assert metrics.estimated_cost_usd is None

    empty_file_change = CodingMetricsCollector.calculate_patch_metrics({}, {"empty.py": ""})
    assert empty_file_change["files_changed"] == 1
    assert empty_file_change["patch_size"] == 0


@pytest.mark.parametrize(
    ("agent", "tests", "reviewer_approved", "expected"),
    [
        (make_agent(success=False, error="request timed out"), make_tests(), None, FailureCategory.TIMEOUT),
        (make_agent(success=False, error="Malformed JSON response"), make_tests(), None, FailureCategory.MALFORMED_RESPONSE),
        (make_agent(success=False, error="Maximum iterations reached"), make_tests(), None, FailureCategory.MAX_ITERATIONS),
        (make_agent(success=False, error="provider failed"), make_tests(), None, FailureCategory.AGENT_ERROR),
        (make_agent(tool_success=False), make_tests(), None, FailureCategory.TOOL_ERROR),
        (make_agent(), make_tests(regression=True), None, FailureCategory.REGRESSION),
        (make_agent(), make_tests(visible=False), None, FailureCategory.VISIBLE_TEST_FAILURE),
        (make_agent(), make_tests(hidden=False), None, FailureCategory.HIDDEN_TEST_FAILURE),
        (make_agent(), make_tests(), False, FailureCategory.REVIEWER_REJECTION),
    ],
)
def test_failure_categories(
    agent: CodingAgentResult,
    tests: CodingTestResult,
    reviewer_approved: bool | None,
    expected: FailureCategory,
) -> None:
    metrics = CodingMetricsCollector().collect(
        agent,
        tests,
        {},
        {},
        task_success=False,
        reviewer_approved=reviewer_approved,
    )
    assert metrics.failure_category is expected


def test_invalid_numeric_metrics_rejected() -> None:
    with pytest.raises(ValidationError):
        CodingMetrics(
            task_success=False,
            regression_detected=False,
            tool_calls=-1,
            runtime_ms=0,
            files_changed=0,
            lines_added=0,
            lines_removed=0,
            patch_size=0,
            failure_category="unknown",
        )
