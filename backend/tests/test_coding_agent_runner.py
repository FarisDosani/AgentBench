import json
from collections.abc import Callable
from pathlib import Path

import pytest

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


def make_runner(
    tmp_path: Path,
    llm: FakeLLM,
    allowed: list[str] | None = None,
    run_tests_callback: Callable[[], object] | None = None,
    max_iterations: int = 10,
) -> CodingAgentRunner:
    workspace = RepositoryWorkspace(tmp_path)
    toolset = CodingToolset(
        workspace,
        allowed or ["list_files", "read_file", "search_repo", "write_file"],
        run_tests_callback=run_tests_callback,
    )
    return CodingAgentRunner(
        llm,
        toolset,
        max_iterations=max_iterations,
        agent_name="agent-a",
    )


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


def test_canonical_list_files_and_final_protocol_are_unchanged(tmp_path: Path) -> None:
    llm = FakeLLM(
        [
            {"type": "tool", "tool": "list_files", "arguments": {}},
            {"type": "final", "answer": "Done"},
        ]
    )

    result = make_runner(tmp_path, llm).run(make_task())

    assert result.success is True
    assert result.final_answer == "Done"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "list_files"
    assert result.tool_calls[0].arguments == {}


def test_shorthand_list_files_is_normalized_and_recorded(tmp_path: Path) -> None:
    result = make_runner(
        tmp_path,
        FakeLLM([{"type": "list_files"}, {"type": "final", "answer": "Done"}]),
    ).run(make_task())

    assert result.success is True
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "list_files"
    assert result.tool_calls[0].arguments == {}
    assert result.tool_calls[0].success is True


def test_shorthand_read_file_with_arguments_object(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("value = 1", encoding="utf-8")
    result = make_runner(
        tmp_path,
        FakeLLM(
            [
                {
                    "type": "read_file",
                    "arguments": {"relative_path": "src.py"},
                },
                {"type": "final", "answer": "Done"},
            ]
        ),
    ).run(make_task())

    assert result.success is True
    assert result.tool_calls[0].tool_name == "read_file"
    assert result.tool_calls[0].arguments == {"relative_path": "src.py"}
    assert result.tool_calls[0].output == "value = 1"


def test_shorthand_write_file_with_direct_arguments(tmp_path: Path) -> None:
    result = make_runner(
        tmp_path,
        FakeLLM(
            [
                {
                    "type": "write_file",
                    "relative_path": "new.py",
                    "content": "saved = True",
                },
                {"type": "final", "answer": "Done"},
            ]
        ),
    ).run(make_task())

    assert result.success is True
    assert result.tool_calls[0].tool_name == "write_file"
    assert result.tool_calls[0].arguments == {
        "relative_path": "new.py",
        "content": "saved = True",
    }
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "saved = True"


def test_shorthand_search_repo_with_direct_arguments(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("find this", encoding="utf-8")
    result = make_runner(
        tmp_path,
        FakeLLM(
            [
                {"type": "search_repo", "query": "find"},
                {"type": "final", "answer": "Done"},
            ]
        ),
    ).run(make_task())

    assert result.success is True
    assert result.tool_calls[0].tool_name == "search_repo"
    assert result.tool_calls[0].arguments == {"query": "find"}
    assert "src.py" in (result.tool_calls[0].output or "")


def test_shorthand_disallowed_tool_does_not_execute(tmp_path: Path) -> None:
    result = make_runner(
        tmp_path,
        FakeLLM(
            [
                {
                    "type": "write_file",
                    "relative_path": "blocked.py",
                    "content": "unsafe = True",
                }
            ]
        ),
        allowed=["read_file"],
    ).run(make_task())

    assert result.success is False
    assert result.error == "Unknown response type: write_file"
    assert result.tool_calls == []
    assert not (tmp_path / "blocked.py").exists()


@pytest.mark.parametrize(
    "response",
    [
        {"type": "unknown_tool"},
        {"type": "shell", "command": "whoami"},
        {"type": "read_file", "relative_path": "src.py", "shell": "whoami"},
    ],
)
def test_unknown_shell_like_or_ambiguous_shorthand_never_executes(
    tmp_path: Path,
    response: dict[str, object],
) -> None:
    (tmp_path / "src.py").write_text("safe", encoding="utf-8")
    result = make_runner(tmp_path, FakeLLM([response])).run(make_task())

    assert result.success is False
    assert result.tool_calls == []
    assert result.error is not None


def test_shorthand_cannot_bypass_hidden_test_isolation(tmp_path: Path) -> None:
    hidden_directory = tmp_path / "hidden_tests"
    hidden_directory.mkdir()
    (hidden_directory / "test_secret.py").write_text("SECRET", encoding="utf-8")
    result = make_runner(
        tmp_path,
        FakeLLM(
            [
                {
                    "type": "read_file",
                    "relative_path": "hidden_tests/test_secret.py",
                },
                {"type": "final", "answer": "Stopped"},
            ]
        ),
    ).run(make_task())

    assert result.tool_calls[0].tool_name == "read_file"
    assert result.tool_calls[0].success is False
    assert "Hidden tests" in (result.tool_calls[0].error or "")
    assert "SECRET" not in (result.tool_calls[0].output or "")


def test_run_tests_result_is_returned_and_counted_as_successful_tool_call(
    tmp_path: Path,
) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )

    def run_visible_tests() -> dict[str, object]:
        return {
            "exit_code": 0,
            "passed": True,
            "timed_out": False,
            "stdout": "3 passed",
            "stderr": "visible warning",
        }

    llm = FakeLLM(
        [
            {"type": "tool", "tool": "run_tests", "arguments": {}},
            {"type": "final", "answer": "Validated"},
        ]
    )
    result = make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=run_visible_tests,
    ).run(task)

    assert result.success is True
    assert result.tool_calls[0].tool_name == "run_tests"
    assert result.tool_calls[0].success is True
    assert '"passed": true' in (result.tool_calls[0].output or "")
    returned_context = llm.messages[1][-1]["content"]
    assert "3 passed" in returned_context
    assert "visible warning" in returned_context


def test_failed_visible_tests_are_valid_tool_output_not_infrastructure_failure(
    tmp_path: Path,
) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )

    def run_visible_tests() -> dict[str, object]:
        return {
            "exit_code": 1,
            "passed": False,
            "timed_out": False,
            "stdout": "assertion failed",
            "stderr": "visible traceback",
        }

    llm = FakeLLM(
        [
            {"type": "run_tests"},
            {"type": "final", "answer": "Unable to improve further"},
        ]
    )
    result = make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=run_visible_tests,
    ).run(task)

    assert result.success is False
    assert result.error == "Visible tests did not pass"
    assert result.final_answer == "Unable to improve further"
    assert result.tool_calls[0].success is True
    assert "assertion failed" in llm.messages[1][-1]["content"]


def test_final_after_write_is_deferred_until_visible_tests_run(
    tmp_path: Path,
) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )
    llm = FakeLLM(
        [
            {
                "type": "tool",
                "tool": "write_file",
                "arguments": {"relative_path": "fixed.py", "content": "fixed = True"},
            },
            {"type": "final", "answer": "Done too early"},
            {"type": "tool", "tool": "run_tests", "arguments": {}},
            {"type": "final", "answer": "Done after tests"},
        ]
    )
    result = make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=lambda: {
            "exit_code": 0,
            "passed": True,
            "timed_out": False,
            "stdout": "passed",
            "stderr": "",
        },
    ).run(task)

    assert result.success is True
    assert result.final_answer == "Done after tests"
    assert result.iterations == 4
    assert [call.tool_name for call in result.tool_calls] == [
        "write_file",
        "run_tests",
    ]
    assert "validation_required" in llm.messages[2][-1]["content"]


def test_write_test_fail_edit_test_pass_then_final(tmp_path: Path) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )
    visible_results = iter(
        [
            {
                "exit_code": 1,
                "passed": False,
                "timed_out": False,
                "stdout": "first visible failure",
                "stderr": "VISIBLE ONLY",
            },
            {
                "exit_code": 0,
                "passed": True,
                "timed_out": False,
                "stdout": "all visible tests passed",
                "stderr": "",
            },
        ]
    )
    llm = FakeLLM(
        [
            {
                "type": "write_file",
                "relative_path": "fixed.py",
                "content": "attempt = 1",
            },
            {"type": "run_tests"},
            {
                "type": "write_file",
                "relative_path": "fixed.py",
                "content": "attempt = 2",
            },
            {"type": "run_tests"},
            {"type": "final", "answer": "Visible tests pass"},
        ]
    )
    result = make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=lambda: next(visible_results),
    ).run(task)

    assert result.success is True
    assert [call.tool_name for call in result.tool_calls] == [
        "write_file",
        "run_tests",
        "write_file",
        "run_tests",
    ]
    assert "first visible failure" in llm.messages[2][-1]["content"]
    assert "all visible tests passed" in llm.messages[4][-1]["content"]
    assert (tmp_path / "fixed.py").read_text(encoding="utf-8") == "attempt = 2"


def test_run_tests_conversation_never_receives_hidden_output(tmp_path: Path) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )
    llm = FakeLLM(
        [
            {"type": "run_tests"},
            {"type": "final", "answer": "Done"},
        ]
    )
    result = make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=lambda: {
            "exit_code": 0,
            "passed": True,
            "timed_out": False,
            "stdout": "VISIBLE OUTPUT",
            "stderr": "",
        },
    ).run(task)

    assert result.success is True
    conversation = json.dumps(llm.messages)
    assert "VISIBLE OUTPUT" in conversation
    assert "hidden-secret" not in conversation
    assert "HIDDEN OUTPUT" not in conversation


def test_completion_guard_respects_max_iterations(tmp_path: Path) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )
    llm = FakeLLM(
        [
            {
                "type": "write_file",
                "relative_path": "fixed.py",
                "content": "fixed = True",
            },
            {"type": "final", "answer": "Done too early"},
        ]
    )
    result = make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=lambda: {},
        max_iterations=2,
    ).run(task)

    assert result.success is False
    assert result.error == "Maximum iterations reached"
    assert [call.tool_name for call in result.tool_calls] == ["write_file"]


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


def test_plain_and_single_fenced_json_responses_are_accepted(tmp_path: Path) -> None:
    plain = make_runner(
        tmp_path,
        FakeLLM(['  {"type":"final","answer":"plain"}\n']),
    ).run(make_task())
    fenced = make_runner(
        tmp_path,
        FakeLLM(['```json\n{"type":"final","answer":"fenced"}\n```']),
    ).run(make_task())

    assert plain.success is True
    assert plain.final_answer == "plain"
    assert fenced.success is True
    assert fenced.final_answer == "fenced"


@pytest.mark.parametrize(
    "response",
    [
        'Here is JSON: {"type":"final","answer":"no"}',
        '{"type":"final","answer":"one"} {"type":"final","answer":"two"}',
        '```json\n{"type":"final","answer":"one"}\n```\n```json\n'
        '{"type":"final","answer":"two"}\n```',
    ],
)
def test_ambiguous_or_prose_wrapped_json_is_rejected(
    tmp_path: Path,
    response: str,
) -> None:
    result = make_runner(tmp_path, FakeLLM([response])).run(make_task())

    assert result.success is False
    assert "Malformed JSON" in (result.error or "")


def test_prompt_lists_exact_schemas_for_only_available_tools(tmp_path: Path) -> None:
    llm = FakeLLM([{"type": "final", "answer": "done"}])
    task = make_task().model_copy(
        update={"allowed_tools": ["list_files", "read_file"]}
    )

    result = make_runner(tmp_path, llm, allowed=["list_files", "read_file"]).run(task)

    assert result.success is True
    system_prompt = llm.messages[0][0]["content"]
    assert "Inspect the repository before deciding what to change" in system_prompt
    assert "You MUST respond with exactly one JSON object" in system_prompt
    assert '{"type":"tool","tool":"TOOL_NAME","arguments":{...}}' in system_prompt
    assert 'Do not put the tool name in "type"' in system_prompt
    assert '{"type":"final","answer":"..."}' in system_prompt
    assert "content argument replaces the complete file" in system_prompt
    assert "read each changed file back" in system_prompt
    assert 'list_files:\n{}' in system_prompt
    assert 'read_file:\n{"relative_path":"..."}' in system_prompt
    assert "search_repo:" not in system_prompt
    assert "write_file:" not in system_prompt
    assert "run_tests" not in system_prompt


def test_prompt_advertises_controlled_visible_test_workflow(tmp_path: Path) -> None:
    task = make_task().model_copy(
        update={"allowed_tools": [*make_task().allowed_tools, "run_tests"]}
    )
    llm = FakeLLM([{"type": "final", "answer": "done"}])

    make_runner(
        tmp_path,
        llm,
        allowed=task.allowed_tools,
        run_tests_callback=lambda: {},
    ).run(task)

    system_prompt = llm.messages[0][0]["content"]
    assert "run_tests:\n{}" in system_prompt
    assert "Visible benchmark tests are read-only" in system_prompt
    assert "search for related functions or usages before editing" in system_prompt
    assert "run visible tests at least once after the final code modification" in system_prompt
    assert "instead of overfitting to visible assertions" in system_prompt
    assert "Hidden tests are unavailable and must not be requested" in system_prompt


def test_llm_error_after_tool_calls_is_preserved(tmp_path: Path) -> None:
    class RateLimitedLLM:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, messages: list[dict[str, str]]) -> str:
            self.calls += 1
            if self.calls == 1:
                return json.dumps(
                    {"type": "tool", "tool": "list_files", "arguments": {}}
                )
            raise RuntimeError("429 Too Many Requests")

    result = make_runner(tmp_path, RateLimitedLLM()).run(make_task())

    assert result.success is False
    assert result.iterations == 2
    assert [call.tool_name for call in result.tool_calls] == ["list_files"]
    assert result.error == "LLM error: 429 Too Many Requests"


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
