import pytest
from pydantic import ValidationError

from app.models.coding_agent import CodingAgentResult
from app.models.coding_task import CodingTask
from app.models.plan import AgentPlan, PlanStep
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult
from app.strategies.planner_executor import PlannerExecutorStrategy


def make_task() -> CodingTask:
    return CodingTask(
        id="task-1",
        name="Plan task",
        description="Implement the fix.",
        repository_path="repo",
        difficulty="medium",
        visible_test_command="pytest visible",
        hidden_test_command="pytest hidden-secret",
    )


def make_agent_result(success: bool = True) -> CodingAgentResult:
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


def make_test_result(*, passed: bool = True, regression: bool = False) -> CodingTestResult:
    command = CommandResult(
        command="pytest visible",
        exit_code=0 if passed else 1,
        stdout="visible",
        stderr="",
        passed=passed,
        timed_out=False,
        duration_ms=1,
    )
    return CodingTestResult(
        visible=command,
        hidden=None,
        visible_passed=passed,
        hidden_passed=None,
        all_passed=passed,
        regression_detected=regression,
    )


class FakeAgentRunner:
    def __init__(self, results: list[CodingAgentResult], events: list[str]) -> None:
        self.results = iter(results)
        self.contexts: list[str | None] = []
        self.events = events

    def run(self, task: CodingTask, extra_context: str | None = None) -> CodingAgentResult:
        self.events.append("agent")
        self.contexts.append(extra_context)
        return next(self.results)


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
        return self.after


def make_plan() -> AgentPlan:
    return AgentPlan(
        task_id="task-1",
        summary="Two-step fix",
        steps=[
            PlanStep(id=1, description="Inspect code"),
            PlanStep(id=2, description="Apply fix"),
        ],
    )


def test_plan_creation_and_ordered_multi_step_success() -> None:
    events: list[str] = []
    plan = make_plan()
    agent = FakeAgentRunner([make_agent_result(), make_agent_result()], events)
    strategy = PlannerExecutorStrategy(
        lambda task: plan,
        agent,  # type: ignore[arg-type]
        FakeTestRunner(make_test_result(), events),  # type: ignore[arg-type]
    )

    result = strategy.run(make_task())

    assert result.success is True
    assert result.strategy_name == "planner_executor"
    assert events == ["baseline", "agent", "agent", "post"]
    assert agent.contexts == ["Plan step 1: Inspect code", "Plan step 2: Apply fix"]
    assert all(step.completed for step in result.plan.steps)
    assert all("hidden-secret" not in (context or "") for context in agent.contexts)


def test_agent_failure_stops_steps_but_runs_post_tests() -> None:
    events: list[str] = []
    agent = FakeAgentRunner([make_agent_result(False)], events)
    result = PlannerExecutorStrategy(
        lambda task: make_plan(),
        agent,  # type: ignore[arg-type]
        FakeTestRunner(make_test_result(), events),  # type: ignore[arg-type]
    ).run(make_task())

    assert result.success is False
    assert len(result.agent_results) == 1
    assert events == ["baseline", "agent", "post"]


def test_test_failure_and_regression_fail_strategy() -> None:
    for after in [make_test_result(passed=False), make_test_result(regression=True)]:
        events: list[str] = []
        result = PlannerExecutorStrategy(
            lambda task: AgentPlan(
                task_id="task-1",
                summary="One step",
                steps=[PlanStep(id=1, description="Fix")],
            ),
            FakeAgentRunner([make_agent_result()], events),  # type: ignore[arg-type]
            FakeTestRunner(after, events),  # type: ignore[arg-type]
        ).run(make_task())
        assert result.success is False


def test_duplicate_ids_and_empty_plan_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentPlan(
            task_id="task-1",
            summary="Duplicate",
            steps=[PlanStep(id=1, description="A"), PlanStep(id=1, description="B")],
        )
    with pytest.raises(ValidationError):
        AgentPlan(task_id="task-1", summary="Empty", steps=[])
