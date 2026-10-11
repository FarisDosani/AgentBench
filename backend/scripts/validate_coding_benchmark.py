import argparse
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.coding_benchmark_run import StrategyBenchmarkResult
from app.models.coding_task import CodingTask
from app.models.test_result import CodingTestResult
from app.core.paths import BACKEND_ROOT, CODING_BENCHMARK_DIRECTORY
from app.services.coding_benchmark_runner import CodingBenchmarkRunner
from app.services.coding_llm_adapter import create_coding_llm_adapter
from app.services.coding_metrics import CodingMetricsCollector
from app.services.coding_strategy_factory import CodingStrategyFactory
from app.services.coding_task_loader import CodingTaskLoader
from app.services.coding_test_runner import CodingTestRunner
from app.services.docker_environment import DockerEnvironment
from app.services.repository_workspace import RepositoryWorkspace


DEFAULT_TASK = "easy-arithmetic-helper"
BUILD_COMMAND = "docker build -f docker/agentbench-python.Dockerfile -t agentbench-python ."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a coding benchmark end to end")
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument(
        "--provider",
        choices=["gemini", "omniroute", "openrouter"],
        default="gemini",
    )
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument(
        "--strategy",
        choices=["direct", "planner_executor", "reviewer"],
        default="direct",
    )
    parser.add_argument("--docker-image", default="agentbench-python")
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--keep-workspace", action="store_true")
    parser.add_argument(
        "--benchmarks",
        default=CODING_BENCHMARK_DIRECTORY,
        help=argparse.SUPPRESS,
    )
    return parser


def snapshot_repository(path: str | Path) -> dict[str, bytes]:
    workspace = RepositoryWorkspace(path)
    snapshot: dict[str, bytes] = {}
    for relative_path in workspace.list_files():
        snapshot[relative_path] = workspace.resolve_path(relative_path).read_bytes()
    return snapshot


def check_docker(image: str) -> tuple[bool, bool]:
    environment = DockerEnvironment(BACKEND_ROOT, image=image, timeout_seconds=30)
    available = environment.is_docker_available()
    return available, available and environment.is_image_available()


def run_baseline(task: CodingTask, docker_image: str) -> CodingTestResult:
    temporary_root = Path(tempfile.mkdtemp(prefix="agentbench-baseline-")).resolve()
    workspace_path = temporary_root / "repository"
    try:
        shutil.copytree(
            Path(task.repository_path),
            workspace_path,
            ignore=CodingBenchmarkRunner._ignore_symlinks,
        )
        copied_task = task.model_copy(update={"repository_path": str(workspace_path)})
        environment = DockerEnvironment(
            workspace_path,
            image=docker_image,
            timeout_seconds=task.timeout_seconds,
        )
        return CodingTestRunner(environment).run_baseline(copied_task)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def run_selected_strategy(
    task: CodingTask,
    *,
    provider: str,
    model: str,
    strategy: str,
    docker_image: str,
    max_iterations: int,
    keep_workspace: bool,
) -> StrategyBenchmarkResult:
    adapter = create_coding_llm_adapter(provider, model)
    key_names = {
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    if provider in key_names and not getattr(adapter.provider, "api_key", "").strip():
        raise ValueError(f"{key_names[provider]} is required")
    factory = CodingStrategyFactory(
        adapter,
        docker_image=docker_image,
        max_iterations=max_iterations,
    )
    runner = CodingBenchmarkRunner(
        factory.direct,
        factory.planner_executor,
        factory.reviewer,
        CodingMetricsCollector(),
        keep_workspaces=keep_workspace,
    )
    result = runner.run_task(task, [strategy])
    return result.strategy_results[0]


def _print_report(
    args: argparse.Namespace,
    task: CodingTask,
    baseline: CodingTestResult,
    strategy_result: StrategyBenchmarkResult,
    original_unchanged: bool,
    validation_success: bool,
) -> None:
    metrics = strategy_result.metrics
    post = strategy_result.test_result
    agent = strategy_result.agent_result
    print(f"Task ID: {task.id}")
    print(f"Difficulty: {task.difficulty.value}")
    print(f"Provider: {args.provider}")
    print(f"Model: {args.model}")
    print(f"Strategy: {args.strategy}")
    print("Docker available: True")
    print(f"Baseline visible passed: {baseline.visible_passed}")
    print(f"Baseline hidden passed: {baseline.hidden_passed}")
    print(f"Agent success: {strategy_result.agent_success}")
    if not strategy_result.agent_success:
        error = agent.error if agent is not None else strategy_result.error
        concise_error = " ".join((error or "Unavailable").split())
        print(f"Agent error: {concise_error[:500]}")
    if agent is not None:
        tool_statuses = ", ".join(
            f"{call.tool_name}:{'success' if call.success else 'failed'}"
            for call in agent.tool_calls
        )
        print(f"Tool call status: {tool_statuses or 'none'}")
        print(f"Final iteration count: {agent.iterations}")
    else:
        print("Tool call status: unavailable")
        print("Final iteration count: unavailable")
    print(f"Post visible passed: {post.visible_passed}")
    print(f"Post hidden passed: {post.hidden_passed}")
    print(f"Regression detected: {post.regression_detected}")
    print(f"Tool calls: {metrics.tool_calls}")
    print(f"Runtime: {metrics.runtime_ms:.2f} ms")
    print(f"Files changed: {metrics.files_changed}")
    print(f"Lines added: {metrics.lines_added}")
    print(f"Lines removed: {metrics.lines_removed}")
    print(f"Patch size: {metrics.patch_size}")
    print(f"Failure category: {metrics.failure_category.value}")
    print(f"Original fixture unchanged: {original_unchanged}")
    if args.keep_workspace:
        print(f"Kept workspace: {strategy_result.workspace_path}")
    print(f"Validation success: {validation_success}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_iterations <= 0:
        print("Error: max-iterations must be greater than zero", file=sys.stderr)
        return 2

    docker_available, image_available = check_docker(args.docker_image)
    if not docker_available:
        print("Docker available: False")
        print("Error: Docker Desktop/Engine is not available", file=sys.stderr)
        return 2
    if not image_available:
        print("Docker available: True")
        print(f"Docker image is missing. Build it with:\n{BUILD_COMMAND}", file=sys.stderr)
        return 2

    try:
        tasks = CodingTaskLoader.load_directory(args.benchmarks)
        task = next((item for item in tasks if item.id == args.task), None)
        if task is None:
            print(f"Error: coding task not found: {args.task}", file=sys.stderr)
            return 2

        original_snapshot = snapshot_repository(task.repository_path)
        baseline = run_baseline(task, args.docker_image)
        strategy_result = run_selected_strategy(
            task,
            provider=args.provider,
            model=args.model,
            strategy=args.strategy,
            docker_image=args.docker_image,
            max_iterations=args.max_iterations,
            keep_workspace=args.keep_workspace,
        )
        original_unchanged = snapshot_repository(task.repository_path) == original_snapshot
    except (OSError, ValueError) as exception:
        print(f"Error: {exception}", file=sys.stderr)
        return 2

    baseline_fails = not baseline.all_passed
    post = strategy_result.test_result
    validation_success = (
        baseline_fails
        and strategy_result.success
        and strategy_result.agent_success
        and post.visible_passed
        and post.hidden_passed is True
        and not post.regression_detected
        and original_unchanged
    )
    _print_report(
        args,
        task,
        baseline,
        strategy_result,
        original_unchanged,
        validation_success,
    )
    return 0 if validation_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
