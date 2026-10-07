import pytest
from pydantic import ValidationError

from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask


def test_valid_agent_config_creation() -> None:
    config = AgentConfig(
        name="researcher",
        model="example-model",
        system_prompt="Answer accurately.",
        temperature=0.5,
        max_tokens=2048,
        tools=["search"],
    )

    assert config.name == "researcher"
    assert config.temperature == 0.5
    assert config.tools == ["search"]


def test_valid_benchmark_task_creation() -> None:
    task = BenchmarkTask(
        id="task-1",
        name="Simple task",
        description="Answer a simple question.",
        input="What is 2 + 2?",
        expected_output="4",
        allowed_tools=["calculator"],
        timeout_seconds=30,
    )

    assert task.id == "task-1"
    assert task.expected_output == "4"
    assert task.timeout_seconds == 30


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_invalid_temperature_rejected(temperature: float) -> None:
    with pytest.raises(ValidationError):
        AgentConfig(name="agent", model="model", temperature=temperature)


def test_invalid_max_tokens_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(name="agent", model="model", max_tokens=0)


def test_invalid_timeout_seconds_rejected() -> None:
    with pytest.raises(ValidationError):
        BenchmarkTask(
            id="task-1",
            name="Task",
            description="Description",
            input="Input",
            timeout_seconds=0,
        )


@pytest.mark.parametrize("field", ["name", "model"])
def test_agent_required_empty_string_fields_rejected(field: str) -> None:
    values = {"name": "agent", "model": "model", field: "   "}

    with pytest.raises(ValidationError):
        AgentConfig(**values)


@pytest.mark.parametrize("field", ["id", "name", "description", "input"])
def test_task_required_empty_string_fields_rejected(field: str) -> None:
    values = {
        "id": "task-1",
        "name": "Task",
        "description": "Description",
        "input": "Input",
        field: "   ",
    }

    with pytest.raises(ValidationError):
        BenchmarkTask(**values)
