import argparse

from app.models.agent import AgentConfig
from app.services.benchmark_runner import BenchmarkRunner
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_benchmark(args)


if __name__ == "__main__":
    raise SystemExit(main())
