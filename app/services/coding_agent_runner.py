import json
import re
import time
from collections.abc import Callable

from app.models.coding_agent import CodingAgentResult, ToolCallRecord
from app.models.coding_task import CodingTask
from app.services.coding_tools import CodingToolset


CodingLLM = Callable[[list[dict[str, str]]], str]

TOOL_SCHEMAS = {
    "list_files": 'list_files:\n{}',
    "read_file": 'read_file:\n{"relative_path":"..."}',
    "search_repo": 'search_repo:\n{"query":"..."}',
    "write_file": 'write_file:\n{"relative_path":"...","content":"..."}',
    "run_tests": 'run_tests:\n{}',
}

TOOL_ARGUMENT_NAMES = {
    "list_files": set(),
    "read_file": {"relative_path"},
    "search_repo": {"query"},
    "write_file": {"relative_path", "content"},
    "run_tests": set(),
}

FENCED_JSON_PATTERN = re.compile(
    r"\A```json\s*(\{.*\})\s*```\Z",
    flags=re.IGNORECASE | re.DOTALL,
)


class CodingAgentRunner:
    def __init__(
        self,
        llm: CodingLLM,
        toolset: CodingToolset,
        max_iterations: int = 20,
        agent_name: str = "coding-agent",
    ) -> None:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be greater than zero")
        self.llm = llm
        self.toolset = toolset
        self.max_iterations = max_iterations
        self.agent_name = agent_name

    def run(
        self,
        task: CodingTask,
        extra_context: str | None = None,
    ) -> CodingAgentResult:
        started_at = time.perf_counter()
        tool_calls: list[ToolCallRecord] = []
        messages = self._initial_messages(task, extra_context)
        available_tools = {
            name for name in task.allowed_tools if self.toolset.has_tool(name)
        }
        repository_modified = False
        tests_ran_after_latest_write = False
        latest_visible_tests_passed: bool | None = None

        for iteration in range(1, self.max_iterations + 1):
            try:
                raw_response = self.llm(messages)
            except Exception as exception:
                return self._failure(
                    task, tool_calls, iteration, started_at, f"LLM error: {exception}"
                )

            messages.append({"role": "assistant", "content": raw_response})
            try:
                response = self._parse_response(raw_response)
            except (json.JSONDecodeError, TypeError) as exception:
                return self._failure(
                    task,
                    tool_calls,
                    iteration,
                    started_at,
                    f"Malformed JSON response: {exception}",
                )

            if not isinstance(response, dict):
                return self._failure(
                    task, tool_calls, iteration, started_at, "Malformed response object"
                )

            response_type = response.get("type")
            if isinstance(response_type, str) and response_type in available_tools:
                try:
                    response = self._normalize_shorthand_tool(response, response_type)
                except ValueError as exception:
                    return self._failure(
                        task,
                        tool_calls,
                        iteration,
                        started_at,
                        f"Malformed shorthand tool request: {exception}",
                    )
                response_type = "tool"

            if response_type == "final":
                answer = response.get("answer")
                if not isinstance(answer, str):
                    return self._failure(
                        task,
                        tool_calls,
                        iteration,
                        started_at,
                        "Final response answer must be a string",
                    )
                if (
                    "run_tests" in available_tools
                    and repository_modified
                    and not tests_ran_after_latest_write
                ):
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "validation_required": True,
                                    "message": (
                                        "Run visible tests after the latest write_file "
                                        "call before returning a final response."
                                    ),
                                }
                            ),
                        }
                    )
                    continue
                if latest_visible_tests_passed is False:
                    return self._failure(
                        task,
                        tool_calls,
                        iteration,
                        started_at,
                        "Visible tests did not pass",
                        final_answer=answer,
                    )
                return CodingAgentResult(
                    task_id=task.id,
                    agent_name=self.agent_name,
                    success=True,
                    final_answer=answer,
                    tool_calls=tool_calls,
                    iterations=iteration,
                    latency_ms=(time.perf_counter() - started_at) * 1000,
                    error=None,
                )

            if response_type != "tool":
                return self._failure(
                    task,
                    tool_calls,
                    iteration,
                    started_at,
                    f"Unknown response type: {response_type}",
                )

            tool_name = response.get("tool")
            arguments = response.get("arguments")
            if not isinstance(tool_name, str) or not isinstance(arguments, dict):
                return self._failure(
                    task, tool_calls, iteration, started_at, "Malformed tool request"
                )

            try:
                output = self.toolset.execute(tool_name, **arguments)
                output_text = output if isinstance(output, str) else json.dumps(output)
                record = ToolCallRecord(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=True,
                    output=output_text,
                )
                tool_message = {"tool": tool_name, "success": True, "output": output}
                if tool_name == "write_file":
                    repository_modified = True
                    tests_ran_after_latest_write = False
                    latest_visible_tests_passed = None
                elif tool_name == "run_tests":
                    tests_ran_after_latest_write = True
                    if isinstance(output, dict) and isinstance(
                        output.get("passed"), bool
                    ):
                        latest_visible_tests_passed = output["passed"]
            except Exception as exception:
                record = ToolCallRecord(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=False,
                    error=str(exception),
                )
                tool_message = {
                    "tool": tool_name,
                    "success": False,
                    "error": str(exception),
                }

            tool_calls.append(record)
            messages.append(
                {"role": "user", "content": json.dumps(tool_message, default=str)}
            )

        return self._failure(
            task,
            tool_calls,
            self.max_iterations,
            started_at,
            "Maximum iterations reached",
        )

    def _initial_messages(
        self,
        task: CodingTask,
        extra_context: str | None,
    ) -> list[dict[str, str]]:
        available_tools = sorted(
            name for name in task.allowed_tools if self.toolset.has_tool(name)
        )
        tool_schemas = "\n\n".join(
            TOOL_SCHEMAS[name] for name in available_tools
        )
        visible_test_guidance = ""
        if "run_tests" in available_tools:
            visible_test_guidance = (
                " Read the relevant visible tests and search for related functions or "
                "usages before editing. Visible benchmark tests are read-only and must "
                "not be modified. When run_tests is available, run it after code "
                "changes, inspect visible failures, and continue editing until visible "
                "tests pass or no further progress can be made. After visible tests "
                "pass, review nearby code and the task contract for edge cases and "
                "regressions instead of overfitting to visible assertions. Before the "
                "final response, run visible tests at least once after the final code "
                "modification. Hidden tests are unavailable and must not be requested."
            )
        system_prompt = (
            "You are a coding agent working in an isolated repository. Inspect the "
            "repository before deciding what to change. You MUST respond with exactly "
            "one JSON object per turn and no prose. For tool calls use exactly "
            '{"type":"tool","tool":"TOOL_NAME","arguments":{...}}. Do not put '
            'the tool name in "type". For completion use exactly '
            '{"type":"final","answer":"..."}. Use write_file to make '
            "actual repository changes when the task requires them, and do not return "
            "a final response until the required edits are complete. The write_file "
            "content argument replaces the complete file, so preserve unrelated code. "
            "After writing, read each changed file back and verify it against the task "
            f"and visible tests before finishing.{visible_test_guidance} Never access "
            "files except through "
            "the tools listed below. Tool names and exact "
            f"argument objects:\n\n{tool_schemas}"
        )
        context = (
            f"Task ID: {task.id}\n"
            f"Description: {task.description}\n"
            f"Repository: {task.repository_path}\n"
            f"Visible test command: {task.visible_test_command}\n"
            f"Allowed tools: {', '.join(available_tools)}"
        )
        if extra_context:
            context = f"{context}\nAdditional context: {extra_context}"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]

    @staticmethod
    def _parse_response(raw_response: str) -> object:
        if not isinstance(raw_response, str):
            raise TypeError("Model response must be a string")
        stripped = raw_response.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as plain_error:
            fenced_match = FENCED_JSON_PATTERN.fullmatch(stripped)
            if fenced_match is None:
                raise plain_error
            return json.loads(fenced_match.group(1))

    @staticmethod
    def _normalize_shorthand_tool(
        response: dict[str, object],
        tool_name: str,
    ) -> dict[str, object]:
        expected_arguments = TOOL_ARGUMENT_NAMES[tool_name]
        if "arguments" in response:
            if set(response) != {"type", "arguments"}:
                raise ValueError("unexpected keys alongside arguments")
            arguments = response["arguments"]
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be an object")
        else:
            arguments = {
                key: value for key, value in response.items() if key != "type"
            }

        argument_names = set(arguments)
        if argument_names != expected_arguments:
            raise ValueError(
                f"{tool_name} requires arguments: "
                f"{', '.join(sorted(expected_arguments)) or 'none'}"
            )
        return {
            "type": "tool",
            "tool": tool_name,
            "arguments": arguments,
        }

    def _failure(
        self,
        task: CodingTask,
        tool_calls: list[ToolCallRecord],
        iterations: int,
        started_at: float,
        error: str,
        final_answer: str | None = None,
    ) -> CodingAgentResult:
        return CodingAgentResult(
            task_id=task.id,
            agent_name=self.agent_name,
            success=False,
            final_answer=final_answer,
            tool_calls=tool_calls,
            iterations=iterations,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            error=error,
        )
