from app.models.coding_agent import CodingAgentResult
from app.models.coding_task import CodingTask
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult
from app.strategies.direct import DirectStrategy


def make_task() -> CodingTask:
    return CodingTask(
        id="task-1",
        name="Fix code",
        description="Fix the implementation.",
        repository_path="repo",
        difficulty="easy",
        visible_test_command="pytest visible",
        hidden_test_command="pytest hidden-secret",
    )


def agent_result(success: bool = True) -> CodingAgentResult:
    return CodingAgentResult(
        task_id="task-1",
        agent_name="agent",
        success=success,
        final_answer="done" if success else None,
        tool_calls=[],
        iterations=1,
        latency_ms=1,
        error=None if success else "failed",
    )


def make_test_result(
    *,
    visible: bool = True,
    hidden: bool | None = True,
    regression: bool = False,
) -> CodingTestResult:
    visible_result = CommandResult(
        command="pytest visible",
        exit_code=0 if visible else 1,
        stdout="visible output",
        stderr="",
        passed=visible,
        timed_out=False,
        duration_ms=1,
    )
    hidden_result = None
    if hidden is not None:
        hidden_result = CommandResult(
            command="pytest hidden-secret",
            exit_code=0 if hidden else 1,
            stdout="hidden output",
            stderr="",
            passed=hidden,
            timed_out=False,
            duration_ms=1,
        )
    return CodingTestResult(
        visible=visible_result,
        hidden=hidden_result,
        visible_passed=visible,
        hidden_passed=hidden,
        all_passed=visible and hidden is not False,
        regression_detected=regression,
    )


class FakeAgentRunner:
    def __init__(self, result: CodingAgentResult, events: list[str]) -> None:
        self.result = result
        self.events = events
        self.received_context = None

    def run(self, task: CodingTask, extra_context=None) -> CodingAgentResult:
        self.events.append("agent")
        self.received_context = extra_context
        return self.result


class FakeTestRunner:
    def __init__(self, after: CodingTestResult, events: list[str]) -> None:
        self.baseline = make_test_result()
        self.after = after
        self.events = events

    def run_baseline(self, task: CodingTask) -> CodingTestResult:
        self.events.append("baseline")
        return self.baseline

    def run_after_changes(self, task: CodingTask, baseline: CodingTestResult) -> CodingTestResult:
        self.events.append("post")
        assert baseline is self.baseline
        return self.after


def run_strategy(
    after: CodingTestResult,
    agent: CodingAgentResult | None = None,
):
    events: list[str] = []
    agent_runner = FakeAgentRunner(agent or agent_result(), events)
    strategy = DirectStrategy(agent_runner, FakeTestRunner(after, events))  # type: ignore[arg-type]
    result = strategy.run(make_task())
    return result, events, agent_runner


def test_successful_solve_and_order() -> None:
    result, events, agent_runner = run_strategy(make_test_result())
    assert result.success is True
    assert result.strategy_name == "direct"
    assert result.task_id == "task-1"
    assert events == ["baseline", "agent", "post"]
    assert agent_runner.received_context is None


def test_agent_failure() -> None:
    result, _, _ = run_strategy(make_test_result(), agent_result(False))
    assert result.success is False


def test_visible_hidden_and_regression_failures() -> None:
    assert run_strategy(make_test_result(visible=False))[0].success is False
    assert run_strategy(make_test_result(hidden=False))[0].success is False
    assert run_strategy(make_test_result(regression=True))[0].success is False
