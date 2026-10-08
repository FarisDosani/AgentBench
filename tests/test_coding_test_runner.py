from app.models.coding_task import CodingTask
from app.models.docker_result import DockerCommandResult
from app.services.coding_test_runner import CodingTestRunner


def make_task(hidden: str | None = None) -> CodingTask:
    return CodingTask(
        id="coding-1",
        name="Coding task",
        description="Fix the code.",
        repository_path="repo",
        difficulty="easy",
        visible_test_command='pytest "tests/test visible.py" -q',
        hidden_test_command=hidden,
    )


def command_result(
    exit_code: int = 0,
    *,
    stdout: str = "ok",
    stderr: str = "",
    timed_out: bool = False,
) -> DockerCommandResult:
    return DockerCommandResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_ms=2.0,
    )


class FakeEnvironment:
    def __init__(self, results: list[DockerCommandResult]) -> None:
        self.results = iter(results)
        self.commands: list[list[str]] = []

    def run_command(self, command: list[str]) -> DockerCommandResult:
        self.commands.append(command)
        return next(self.results)


def test_visible_pass_and_command_parsing() -> None:
    environment = FakeEnvironment([command_result()])
    result = CodingTestRunner(environment).run_baseline(make_task())  # type: ignore[arg-type]

    assert environment.commands == [["pytest", "tests/test visible.py", "-q"]]
    assert result.visible_passed is True
    assert result.hidden is None
    assert result.hidden_passed is None
    assert result.all_passed is True


def test_visible_failure_and_timeout() -> None:
    environment = FakeEnvironment([command_result(-1, timed_out=True)])
    result = CodingTestRunner(environment).run_baseline(make_task())  # type: ignore[arg-type]

    assert result.visible.passed is False
    assert result.visible.timed_out is True
    assert result.all_passed is False


def test_hidden_enabled_and_output_kept_separate() -> None:
    environment = FakeEnvironment(
        [command_result(stdout="visible"), command_result(stdout="hidden secret")]
    )
    result = CodingTestRunner(environment).run_baseline(make_task("pytest hidden -q"))  # type: ignore[arg-type]

    assert environment.commands[-1] == ["pytest", "hidden", "-q"]
    assert result.hidden_passed is True
    assert result.all_passed is True
    assert result.visible.stdout == "visible"
    assert "hidden secret" not in result.visible.stdout


def test_hidden_failure_makes_all_failed() -> None:
    environment = FakeEnvironment([command_result(), command_result(1)])
    result = CodingTestRunner(environment).run_baseline(make_task("pytest hidden"))  # type: ignore[arg-type]

    assert result.visible_passed is True
    assert result.hidden_passed is False
    assert result.all_passed is False


def test_visible_regression_and_no_false_regression() -> None:
    environment = FakeEnvironment([command_result(), command_result(1)])
    runner = CodingTestRunner(environment)  # type: ignore[arg-type]
    task = make_task()
    baseline = runner.run_baseline(task)
    after = runner.run_after_changes(task, baseline)
    assert after.regression_detected is True

    environment = FakeEnvironment([command_result(1), command_result(1)])
    runner = CodingTestRunner(environment)  # type: ignore[arg-type]
    baseline = runner.run_baseline(task)
    assert runner.run_after_changes(task, baseline).regression_detected is False


def test_hidden_regression() -> None:
    environment = FakeEnvironment(
        [command_result(), command_result(), command_result(), command_result(1)]
    )
    runner = CodingTestRunner(environment)  # type: ignore[arg-type]
    task = make_task("pytest hidden")
    baseline = runner.run_baseline(task)
    after = runner.run_after_changes(task, baseline)

    assert after.regression_detected is True
