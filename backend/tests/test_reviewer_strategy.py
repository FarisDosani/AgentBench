from app.models.coding_agent import CodingAgentResult, ToolCallRecord
from app.models.coding_task import CodingTask
from app.models.review import ReviewResult
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult
from app.strategies.reviewer import ReviewerStrategy


def make_task() -> CodingTask:
    return CodingTask(
        id="task-1",
        name="Review task",
        description="Implement a reviewed fix.",
        repository_path="repo",
        difficulty="hard",
        visible_test_command="pytest visible",
        hidden_test_command="pytest hidden-secret",
    )


def make_agent_result(success: bool = True) -> CodingAgentResult:
    return CodingAgentResult(
        task_id="task-1",
        agent_name="agent",
        success=success,
        final_answer="done" if success else None,
        tool_calls=[
            ToolCallRecord(
                tool_name="write_file",
                arguments={"relative_path": "src/fix.py", "content": "safe"},
                success=True,
                output="null",
            )
        ],
        iterations=1,
        latency_ms=1,
        error=None if success else "failed",
    )


def make_test_result(passed: bool = True, regression: bool = False) -> CodingTestResult:
    visible = CommandResult(
        command="pytest visible",
        exit_code=0 if passed else 1,
        stdout="visible",
        stderr="",
        passed=passed,
        timed_out=False,
        duration_ms=1,
    )
    return CodingTestResult(
        visible=visible,
        hidden=None,
        visible_passed=passed,
        hidden_passed=None,
        all_passed=passed,
        regression_detected=regression,
    )


class FakeAgent:
    def __init__(self, results: list[CodingAgentResult], events: list[str]) -> None:
        self.results = iter(results)
        self.contexts: list[str | None] = []
        self.events = events

    def run(self, task: CodingTask, extra_context: str | None = None) -> CodingAgentResult:
        self.events.append("agent")
        self.contexts.append(extra_context)
        return next(self.results)


class FakeTests:
    def __init__(self, after: CodingTestResult, events: list[str]) -> None:
        self.baseline = make_test_result()
        self.after = after
        self.events = events

    def run_baseline(self, task: CodingTask) -> CodingTestResult:
        self.events.append("baseline")
        return self.baseline

    def run_after_changes(self, task: CodingTask, baseline: CodingTestResult) -> CodingTestResult:
        self.events.append("post")
        return self.after


def test_immediate_approval() -> None:
    events: list[str] = []
    summaries: list[str] = []

    def reviewer(task: CodingTask, summary: str) -> ReviewResult:
        events.append("review")
        summaries.append(summary)
        return ReviewResult(approved=True, feedback="Looks good", requested_changes=[])

    result = ReviewerStrategy(
        FakeAgent([make_agent_result()], events),  # type: ignore[arg-type]
        reviewer,
        FakeTests(make_test_result(), events),  # type: ignore[arg-type]
    ).run(make_task())

    assert result.success is True
    assert result.strategy_name == "reviewer"
    assert events == ["baseline", "agent", "review", "post"]
    assert summaries == ["Files changed:\n- src/fix.py"]
    assert "hidden" not in summaries[0]


def test_requested_changes_trigger_revision_and_approval() -> None:
    events: list[str] = []
    reviews = iter(
        [
            ReviewResult(approved=False, feedback="Add coverage", requested_changes=["Add a test"]),
            ReviewResult(approved=True, feedback="Approved", requested_changes=[]),
        ]
    )
    agent = FakeAgent([make_agent_result(), make_agent_result()], events)
    result = ReviewerStrategy(
        agent,  # type: ignore[arg-type]
        lambda task, summary: next(reviews),
        FakeTests(make_test_result(), events),  # type: ignore[arg-type]
        max_review_rounds=1,
    ).run(make_task())

    assert result.success is True
    assert len(result.agent_results) == 2
    assert "Add a test" in (agent.contexts[1] or "")
    assert "hidden-secret" not in (agent.contexts[1] or "")


def test_max_rounds_and_rejection() -> None:
    events: list[str] = []
    rejection = ReviewResult(
        approved=False,
        feedback="Still incorrect",
        requested_changes=["Try again"],
    )
    result = ReviewerStrategy(
        FakeAgent([make_agent_result()], events),  # type: ignore[arg-type]
        lambda task, summary: rejection,
        FakeTests(make_test_result(), events),  # type: ignore[arg-type]
        max_review_rounds=0,
    ).run(make_task())

    assert result.success is False
    assert len(result.agent_results) == 1
    assert len(result.reviews) == 1


def test_agent_test_and_regression_failures() -> None:
    approval = lambda task, summary: ReviewResult(
        approved=True, feedback="Approved", requested_changes=[]
    )
    for agent_result, after in [
        (make_agent_result(False), make_test_result()),
        (make_agent_result(), make_test_result(False)),
        (make_agent_result(), make_test_result(True, regression=True)),
    ]:
        events: list[str] = []
        result = ReviewerStrategy(
            FakeAgent([agent_result], events),  # type: ignore[arg-type]
            approval,
            FakeTests(after, events),  # type: ignore[arg-type]
        ).run(make_task())
        assert result.success is False
        assert events[-1] == "post"
