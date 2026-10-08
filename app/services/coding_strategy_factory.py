import json
from pathlib import Path

from app.models.coding_task import CodingTask
from app.models.plan import AgentPlan
from app.models.review import ReviewResult
from app.services.coding_agent_runner import CodingAgentRunner, CodingLLM
from app.services.coding_test_runner import CodingTestRunner
from app.services.coding_tools import CodingToolset
from app.services.docker_environment import DockerEnvironment
from app.services.repository_workspace import RepositoryWorkspace
from app.strategies.direct import DirectStrategy
from app.strategies.planner_executor import PlannerExecutorStrategy
from app.strategies.reviewer import ReviewerStrategy


class CodingStrategyFactory:
    def __init__(
        self,
        llm: CodingLLM,
        docker_image: str = "agentbench-python",
        max_iterations: int = 20,
    ) -> None:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be greater than zero")
        self.llm = llm
        self.docker_image = docker_image
        self.max_iterations = max_iterations

    def direct(self, task: CodingTask, workspace_path: Path) -> DirectStrategy:
        agent_runner, test_runner = self._components(task, workspace_path)
        return DirectStrategy(agent_runner, test_runner)

    def planner_executor(
        self,
        task: CodingTask,
        workspace_path: Path,
    ) -> PlannerExecutorStrategy:
        agent_runner, test_runner = self._components(task, workspace_path)
        return PlannerExecutorStrategy(self._planner, agent_runner, test_runner)

    def reviewer(self, task: CodingTask, workspace_path: Path) -> ReviewerStrategy:
        agent_runner, test_runner = self._components(task, workspace_path)
        return ReviewerStrategy(agent_runner, self._reviewer, test_runner)

    def _components(
        self,
        task: CodingTask,
        workspace_path: Path,
    ) -> tuple[CodingAgentRunner, CodingTestRunner]:
        workspace = RepositoryWorkspace(workspace_path)
        toolset = CodingToolset(workspace, task.allowed_tools)
        environment = DockerEnvironment(
            workspace_path,
            image=self.docker_image,
            timeout_seconds=task.timeout_seconds,
        )
        return (
            CodingAgentRunner(
                self.llm,
                toolset,
                max_iterations=self.max_iterations,
            ),
            CodingTestRunner(environment),
        )

    def _planner(self, task: CodingTask) -> AgentPlan:
        messages = [
            {
                "role": "system",
                "content": (
                    "Return strict JSON for an implementation plan with task_id, "
                    "summary, and a non-empty steps list. Each step requires integer id "
                    "and description. Do not include markdown."
                ),
            },
            {
                "role": "user",
                "content": f"Task ID: {task.id}\nDescription: {task.description}",
            },
        ]
        return AgentPlan.model_validate(json.loads(self.llm(messages)))

    def _reviewer(self, task: CodingTask, change_summary: str) -> ReviewResult:
        messages = [
            {
                "role": "system",
                "content": (
                    "Review the change summary and return strict JSON with approved "
                    "(boolean), feedback (non-empty string), and requested_changes "
                    "(string list). Do not include markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task ID: {task.id}\nDescription: {task.description}\n"
                    f"Change summary:\n{change_summary}"
                ),
            },
        ]
        return ReviewResult.model_validate(json.loads(self.llm(messages)))
