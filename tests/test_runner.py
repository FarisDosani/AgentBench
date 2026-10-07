from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask
from app.services.runner import AgentRunner


def make_agent() -> AgentConfig:
    return AgentConfig(name="test-agent", model="test-model")


def make_task() -> BenchmarkTask:
    return BenchmarkTask(
        id="task-1",
        name="Test task",
        description="A task used to test the runner.",
        input="Test input",
    )


def test_successful_execution() -> None:
    agent = make_agent()
    task = make_task()
    received: list[object] = []

    def executor(received_agent: AgentConfig, received_task: BenchmarkTask) -> str:
        received.extend([received_agent, received_task])
        return "completed output"

    result = AgentRunner(executor).run(agent, task)

    assert received == [agent, task]
    assert result.agent_name == agent.name
    assert result.task_id == task.id
    assert result.success is True
    assert result.output == "completed output"
    assert result.error is None
    assert result.latency_ms >= 0


def test_executor_exception_is_captured() -> None:
    def failing_executor(agent: AgentConfig, task: BenchmarkTask) -> str:
        raise RuntimeError("executor failed")

    result = AgentRunner(failing_executor).run(make_agent(), make_task())

    assert result.success is False
    assert result.output is None
    assert result.error == "executor failed"
    assert result.latency_ms >= 0
