import json
from pathlib import Path

import pytest

from app.models.coding_task import CodingTask
from app.services.coding_llm_adapter import CodingLLMAdapter
from app.services.coding_strategy_factory import CodingStrategyFactory
from app.strategies.direct import DirectStrategy
from app.strategies.planner_executor import PlannerExecutorStrategy
from app.strategies.reviewer import ReviewerStrategy


def make_task(workspace: Path) -> CodingTask:
    return CodingTask(
        id="task-1",
        name="Factory task",
        description="Fix public behavior.",
        repository_path=str(workspace),
        difficulty="medium",
        visible_test_command="pytest -q tests",
        hidden_test_command="pytest -q hidden-secret",
        allowed_tools=["read_file", "write_file"],
        timeout_seconds=123,
    )


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls: list[list[dict[str, str]]] = []

    def __call__(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return next(self.responses)


def test_adapter_forwards_full_conversation() -> None:
    captured = {}

    class Provider:
        def complete_messages(self, messages, **kwargs):
            captured["messages"] = messages
            captured.update(kwargs)
            return "assistant response"

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
        {"role": "assistant", "content": "assistant"},
        {"role": "user", "content": "tool context"},
    ]
    adapter = CodingLLMAdapter(Provider(), "model-x", temperature=0.2, max_tokens=99)  # type: ignore[arg-type]

    assert adapter(messages) == "assistant response"
    assert captured["messages"] is messages
    assert captured["model"] == "model-x"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 99


def test_factory_constructs_all_strategies_with_context(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    factory = CodingStrategyFactory(FakeLLM([]), docker_image="custom", max_iterations=7)

    direct = factory.direct(task, tmp_path)
    planner = factory.planner_executor(task, tmp_path)
    reviewer = factory.reviewer(task, tmp_path)

    assert isinstance(direct, DirectStrategy)
    assert isinstance(planner, PlannerExecutorStrategy)
    assert isinstance(reviewer, ReviewerStrategy)
    assert direct.agent_runner.max_iterations == 7
    assert direct.agent_runner.toolset.allowed_tools == {"read_file", "write_file"}
    assert direct.test_runner.environment.image == "custom"
    assert direct.test_runner.environment.timeout_seconds == 123


def test_planner_and_reviewer_parse_strict_json_without_hidden_data(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    llm = FakeLLM(
        [
            json.dumps(
                {
                    "task_id": "task-1",
                    "summary": "Plan",
                    "steps": [{"id": 1, "description": "Inspect"}],
                }
            ),
            json.dumps(
                {
                    "approved": True,
                    "feedback": "Looks good",
                    "requested_changes": [],
                }
            ),
        ]
    )
    factory = CodingStrategyFactory(llm)

    assert factory._planner(task).steps[0].description == "Inspect"
    assert factory._reviewer(task, "Files changed: a.py").approved is True
    assert all(
        "hidden-secret" not in message["content"]
        for call in llm.calls
        for message in call
    )


@pytest.mark.parametrize("method", ["planner", "reviewer"])
def test_malformed_planner_and_reviewer_output_fails_cleanly(
    tmp_path: Path,
    method: str,
) -> None:
    factory = CodingStrategyFactory(FakeLLM(["not json"]))
    with pytest.raises(json.JSONDecodeError):
        if method == "planner":
            factory._planner(make_task(tmp_path))
        else:
            factory._reviewer(make_task(tmp_path), "safe summary")
