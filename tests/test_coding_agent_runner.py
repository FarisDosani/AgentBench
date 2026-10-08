import json
from pathlib import Path

from app.models.coding_task import CodingTask
from app.services.coding_agent_runner import CodingAgentRunner
from app.services.coding_tools import CodingToolset
from app.services.repository_workspace import RepositoryWorkspace


def make_task() -> CodingTask:
    return CodingTask(
        id="coding-1",
        name="Fix code",
        description="Update the repository.",
        repository_path="repo",
        difficulty="easy",
        visible_test_command="pytest -q",
        hidden_test_command="pytest hidden-secret -q",
        allowed_tools=["list_files", "read_file", "search_repo", "write_file"],
    )


class FakeLLM:
    def __init__(self, responses: list[dict[str, object] | str]) -> None:
        self.responses = iter(responses)
        self.messages: list[list[dict[str, str]]] = []

    def __call__(self, messages: list[dict[str, str]]) -> str:
        self.messages.append([dict(message) for message in messages])
        response = next(self.responses)
        return response if isinstance(response, str) else json.dumps(response)


def make_runner(tmp_path: Path, llm: FakeLLM, allowed: list[str] | None = None) -> CodingAgentRunner:
    workspace = RepositoryWorkspace(tmp_path)
    toolset = CodingToolset(
        workspace,
        allowed or ["list_files", "read_file", "search_repo", "write_file"],
    )
    return CodingAgentRunner(llm, toolset, max_iterations=10, agent_name="agent-a")


def test_multiple_tools_execute_and_outputs_return_to_model(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle", encoding="utf-8")
    llm = FakeLLM(
        [
            {"type": "tool", "tool": "list_files", "arguments": {}},
            {"type": "tool", "tool": "read_file", "arguments": {"relative_path": "a.py"}},
            {"type": "tool", "tool": "search_repo", "arguments": {"query": "needle"}},
            {"type": "tool", "tool": "write_file", "arguments": {"relative_path": "b.py", "content": "done"}},
            {"type": "final", "answer": "Done"},
        ]
    )

    result = make_runner(tmp_path, llm).run(make_task())

    assert result.success is True
    assert result.final_answer == "Done"
    assert result.iterations == 5
    assert [record.tool_name for record in result.tool_calls] == [
        "list_files", "read_file", "search_repo", "write_file"
    ]
    assert all(record.success for record in result.tool_calls)
    assert (tmp_path / "b.py").read_text(encoding="utf-8") == "done"
    assert any("needle" in message["content"] for message in llm.messages[2])
    assert all("hidden-secret" not in message["content"] for message in llm.messages[0])


def test_disallowed_and_unknown_tools_are_recorded(tmp_path: Path) -> None:
    for tool_name in ["write_file", "run_tests"]:
        llm = FakeLLM(
            [
                {"type": "tool", "tool": tool_name, "arguments": {}},
                {"type": "final", "answer": "Stopped"},
            ]
        )
        result = make_runner(tmp_path, llm, allowed=["read_file"]).run(make_task())
        assert result.tool_calls[0].success is False
        assert result.tool_calls[0].error is not None


def test_malformed_json_and_unknown_type_fail_cleanly(tmp_path: Path) -> None:
    malformed = make_runner(tmp_path, FakeLLM(["not json"])).run(make_task())
    assert malformed.success is False
    assert "Malformed JSON" in (malformed.error or "")

    unknown = make_runner(tmp_path, FakeLLM([{"type": "mystery"}])).run(make_task())
    assert unknown.success is False
    assert "Unknown response type" in (unknown.error or "")


def test_max_iterations_and_latency(tmp_path: Path) -> None:
    llm = FakeLLM(
        [{"type": "tool", "tool": "list_files", "arguments": {}}] * 2
    )
    workspace = RepositoryWorkspace(tmp_path)
    runner = CodingAgentRunner(
        llm,
        CodingToolset(workspace, ["list_files"]),
        max_iterations=2,
    )

    result = runner.run(make_task())

    assert result.success is False
    assert result.iterations == 2
    assert result.error == "Maximum iterations reached"
    assert result.latency_ms >= 0
