import argparse
import sys

from app.models.agent import AgentConfig
from app.services.benchmark_runner import BenchmarkRunner
from app.services.coding_benchmark_runner import CodingBenchmarkRunner
from app.services.coding_llm_adapter import create_coding_llm_adapter
from app.services.coding_metrics import CodingMetricsCollector
from app.services.coding_strategy_factory import CodingStrategyFactory
from app.services.coding_task_loader import CodingTaskLoader
from app.services.evaluator import ExactMatchEvaluator
from app.services.gemini_executor import GeminiExecutor
from app.services.omniroute_executor import OmniRouteExecutor
from app.services.result_store import ResultStore
from app.services.runner import AgentRunner
from app.services.task_loader import TaskLoader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run a benchmark through the selected provider"
    )
    run_parser.add_argument("--name", required=True, help="Agent display name")
    run_parser.add_argument("--model", required=True, help="Provider model ID")
    run_parser.add_argument(
        "--provider",
        choices=["gemini", "omniroute"],
        default="gemini",
    )
    run_parser.add_argument("--system-prompt", default=None)
    run_parser.add_argument("--temperature", type=float, default=0.0)
    run_parser.add_argument("--max-tokens", type=int, default=1024)
    run_parser.add_argument("--benchmarks", default="benchmarks")
    run_parser.add_argument("--results", default="results")

    coding_parser = subparsers.add_parser(
        "coding-run", help="Run an isolated coding-agent benchmark"
    )
    coding_parser.add_argument("--task", required=True, help="Coding task ID")
    coding_parser.add_argument(
        "--provider", choices=["gemini", "omniroute"], default="gemini"
    )
    coding_parser.add_argument("--model", required=True, help="Provider model ID")
    coding_parser.add_argument(
        "--strategy",
        action="append",
        help="Strategy name; repeat or provide comma-separated names",
    )
    coding_parser.add_argument("--benchmarks", default="coding_benchmarks")
    coding_parser.add_argument("--docker-image", default="agentbench-python")
    coding_parser.add_argument("--max-iterations", type=int, default=20)
    coding_parser.add_argument("--keep-workspaces", action="store_true")

    return parser


def run_benchmark(args: argparse.Namespace) -> int:
    agent = AgentConfig(
        name=args.name,
        model=args.model,
        system_prompt=args.system_prompt,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    tasks = TaskLoader.load_directory(args.benchmarks)
    executor = GeminiExecutor() if args.provider == "gemini" else OmniRouteExecutor()
    runner = AgentRunner(executor)
    benchmark_runner = BenchmarkRunner(runner, ExactMatchEvaluator())
    result = benchmark_runner.run(agent, tasks)
    saved_path = ResultStore(args.results).save(result)

    print(f"Agent: {agent.name}")
    print(f"Model: {agent.model}")
    print(f"Total tasks: {result.total_tasks}")
    print(f"Passed tasks: {result.passed_tasks}")
    print(f"Failed tasks: {result.failed_tasks}")
    print(f"Average score: {result.average_score:.2f}")
    print(f"Average latency: {result.average_latency_ms:.2f} ms")
    print(f"Saved result: {saved_path}")

    return 0


def _parse_coding_strategies(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    strategies = [name.strip() for value in values for name in value.split(",") if name.strip()]
    supported = {"direct", "planner_executor", "reviewer"}
    unknown = [name for name in strategies if name not in supported]
    if unknown:
        raise ValueError(f"Unknown coding strategy: {unknown[0]}")
    return strategies


def run_coding_benchmark(args: argparse.Namespace) -> int:
    try:
        if args.max_iterations <= 0:
            raise ValueError("max-iterations must be greater than zero")
        tasks = CodingTaskLoader.load_directory(args.benchmarks)
        task = next((item for item in tasks if item.id == args.task), None)
        if task is None:
            print(f"Error: coding task not found: {args.task}", file=sys.stderr)
            return 2

        strategies = _parse_coding_strategies(args.strategy)
        adapter = create_coding_llm_adapter(args.provider, args.model)
        factory = CodingStrategyFactory(
            adapter,
            docker_image=args.docker_image,
            max_iterations=args.max_iterations,
        )
        runner = CodingBenchmarkRunner(
            factory.direct,
            factory.planner_executor,
            factory.reviewer,
            CodingMetricsCollector(),
            keep_workspaces=args.keep_workspaces,
        )
        result = runner.run_task(task, strategies)
    except (OSError, ValueError) as exception:
        print(f"Error: {exception}", file=sys.stderr)
        return 2

    print(f"Task: {result.task_id}")
    print(f"Difficulty: {result.difficulty.value}")
    for strategy in result.strategy_results:
        print(f"\nStrategy: {strategy.strategy_name}")
        print(f"Success: {strategy.success}")
        print(f"Visible tests passed: {strategy.test_result.visible_passed}")
        print(f"Hidden tests passed: {strategy.test_result.hidden_passed}")
        print(f"Regression detected: {strategy.test_result.regression_detected}")
        print(f"Tool calls: {strategy.metrics.tool_calls}")
        print(f"Runtime: {strategy.metrics.runtime_ms:.2f} ms")
        print(f"Files changed: {strategy.metrics.files_changed}")
        print(f"Lines added: {strategy.metrics.lines_added}")
        print(f"Lines removed: {strategy.metrics.lines_removed}")
        print(f"Patch size: {strategy.metrics.patch_size}")
        print(f"Failure category: {strategy.metrics.failure_category.value}")
    print(f"\nBest Strategy: {result.best_strategy or 'None'}")
    return 0 if any(item.success for item in result.strategy_results) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return run_benchmark(args)
    return run_coding_benchmark(args)


if __name__ == "__main__":
    raise SystemExit(main())
