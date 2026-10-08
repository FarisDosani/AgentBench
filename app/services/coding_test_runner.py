import shlex

from app.models.coding_task import CodingTask
from app.models.docker_result import DockerCommandResult
from app.models.test_result import CodingTestResult, TestCommandResult
from app.services.docker_environment import DockerEnvironment


class CodingTestRunner:
    def __init__(self, environment: DockerEnvironment) -> None:
        self.environment = environment

    def run_baseline(self, task: CodingTask) -> CodingTestResult:
        return self._run(task, baseline=None)

    def run_after_changes(
        self,
        task: CodingTask,
        baseline: CodingTestResult,
    ) -> CodingTestResult:
        return self._run(task, baseline=baseline)

    def _run(
        self,
        task: CodingTask,
        baseline: CodingTestResult | None,
    ) -> CodingTestResult:
        visible = self._execute(task.visible_test_command)
        hidden = (
            self._execute(task.hidden_test_command)
            if task.is_hidden_test_enabled and task.hidden_test_command is not None
            else None
        )
        hidden_passed = hidden.passed if hidden is not None else None
        all_passed = visible.passed and (hidden_passed is not False)

        regression_detected = False
        if baseline is not None:
            regression_detected = baseline.visible_passed and not visible.passed
            if (
                baseline.hidden_passed is True
                and hidden_passed is False
            ):
                regression_detected = True

        return CodingTestResult(
            visible=visible,
            hidden=hidden,
            visible_passed=visible.passed,
            hidden_passed=hidden_passed,
            all_passed=all_passed,
            regression_detected=regression_detected,
        )

    def _execute(self, command: str) -> TestCommandResult:
        docker_result = self.environment.run_command(shlex.split(command))
        return self._to_test_result(command, docker_result)

    @staticmethod
    def _to_test_result(
        command: str,
        result: DockerCommandResult,
    ) -> TestCommandResult:
        return TestCommandResult(
            command=command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            passed=result.exit_code == 0 and not result.timed_out,
            timed_out=result.timed_out,
            duration_ms=result.duration_ms,
        )
