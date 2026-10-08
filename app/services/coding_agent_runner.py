import json
import time
from collections.abc import Callable

from app.models.coding_agent import CodingAgentResult, ToolCallRecord
from app.models.coding_task import CodingTask
from app.services.coding_tools import CodingToolset


CodingLLM = Callable[[list[dict[str, str]]], str]


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

        for iteration in range(1, self.max_iterations + 1):
            try:
                raw_response = self.llm(messages)
            except Exception as exception:
                return self._failure(
                    task, tool_calls, iteration, started_at, f"LLM error: {exception}"
                )

            messages.append({"role": "assistant", "content": raw_response})
            try:
                response = json.loads(raw_response)
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
        system_prompt = (
            "You are a coding agent. Respond with exactly one JSON object. "
            'Use {"type":"tool","tool":"name","arguments":{...}} to call a tool, '
            'or {"type":"final","answer":"summary"} when finished. '
            "Never access files except through the provided tools."
        )
        available_tools = sorted(
            name for name in task.allowed_tools if self.toolset.has_tool(name)
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

    def _failure(
        self,
        task: CodingTask,
        tool_calls: list[ToolCallRecord],
        iterations: int,
        started_at: float,
        error: str,
    ) -> CodingAgentResult:
        return CodingAgentResult(
            task_id=task.id,
            agent_name=self.agent_name,
            success=False,
            final_answer=None,
            tool_calls=tool_calls,
            iterations=iterations,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            error=error,
        )
