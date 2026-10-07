import time
from collections.abc import Callable

from app.models.agent import AgentConfig
from app.models.result import AgentRunResult
from app.models.task import BenchmarkTask


Executor = Callable[[AgentConfig, BenchmarkTask], str]


class AgentRunner:
    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def run(self, agent: AgentConfig, task: BenchmarkTask) -> AgentRunResult:
        started_at = time.perf_counter()

        try:
            output = self.executor(agent, task)
        except Exception as exception:
            return AgentRunResult(
                agent_name=agent.name,
                task_id=task.id,
                success=False,
                output=None,
                latency_ms=(time.perf_counter() - started_at) * 1000,
                error=str(exception),
            )

        return AgentRunResult(
            agent_name=agent.name,
            task_id=task.id,
            success=True,
            output=output,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            error=None,
        )
