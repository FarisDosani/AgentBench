import time
from typing import Any

from app.models.tool import ToolExecutionResult
from app.services.tool_registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, tool_name: str, **kwargs: Any) -> ToolExecutionResult:
        started_at = time.perf_counter()

        try:
            tool = self.registry.get(tool_name)
            output = str(tool(**kwargs))
        except Exception as exception:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=str(exception),
                latency_ms=(time.perf_counter() - started_at) * 1000,
            )

        return ToolExecutionResult(
            tool_name=tool_name,
            success=True,
            output=output,
            error=None,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )
