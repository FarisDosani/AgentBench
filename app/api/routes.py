from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.agent import AgentConfig
from app.models.benchmark import BenchmarkRunResult
from app.models.comparison import ComparisonResult
from app.models.coding_api import (
    CodingBenchmarkRequest,
    CodingTaskSummary,
    SafeCodingBenchmarkResponse,
)
from app.models.coding_task import CodingTask
from app.models.task import BenchmarkTask
from app.services.benchmark_runner import BenchmarkRunner
from app.services.coding_benchmark_runner import CodingBenchmarkRunner
from app.services.coding_llm_adapter import create_coding_llm_adapter
from app.services.coding_metrics import CodingMetricsCollector
from app.services.coding_strategy_factory import CodingStrategyFactory
from app.services.coding_task_loader import CodingTaskLoader
from app.services.comparison_service import ComparisonService
from app.services.evaluator import ExactMatchEvaluator
from app.services.omniroute_executor import OmniRouteExecutor
from app.services.result_store import ResultStore
from app.services.runner import AgentRunner
from app.services.task_loader import TaskLoader


router = APIRouter(prefix="/api")
CODING_BENCHMARK_DIRECTORY = "coding_benchmarks"


def _validate_result_filename(filename: str) -> str:
    if (
        not filename
        or ".." in filename
        or "/" in filename
        or "\\" in filename
        or not filename.endswith(".json")
        or Path(filename).name != filename
    ):
        raise HTTPException(status_code=400, detail="Invalid result filename")
    return filename


@router.get("/tasks", response_model=list[BenchmarkTask])
def list_tasks() -> list[BenchmarkTask]:
    return TaskLoader.load_directory("benchmarks")


@router.post("/benchmarks/run", response_model=BenchmarkRunResult)
def run_benchmark(agent: AgentConfig) -> BenchmarkRunResult:
    tasks = TaskLoader.load_directory("benchmarks")
    runner = AgentRunner(OmniRouteExecutor())
    benchmark_runner = BenchmarkRunner(runner, ExactMatchEvaluator())
    result = benchmark_runner.run(agent, tasks)
    ResultStore().save(result)
    return result


@router.get("/results", response_model=list[str])
def list_results() -> list[str]:
    return [path.name for path in ResultStore().list_results()]


@router.get("/results/{filename:path}", response_model=BenchmarkRunResult)
def get_result(filename: str) -> BenchmarkRunResult:
    validated_filename = _validate_result_filename(filename)
    store = ResultStore()
    try:
        return store.load(store.directory / validated_filename)
    except FileNotFoundError as exception:
        raise HTTPException(status_code=404, detail="Result not found") from exception


@router.post("/compare", response_model=ComparisonResult)
def compare_results(filenames: list[str]) -> ComparisonResult:
    store = ResultStore()
    runs: list[BenchmarkRunResult] = []

    for filename in filenames:
        validated_filename = _validate_result_filename(filename)
        try:
            runs.append(store.load(store.directory / validated_filename))
        except FileNotFoundError as exception:
            raise HTTPException(status_code=404, detail="Result not found") from exception

    return ComparisonService().compare(runs)


def _find_coding_task(task_id: str) -> CodingTask:
    tasks = CodingTaskLoader.load_directory(CODING_BENCHMARK_DIRECTORY)
    task = next((item for item in tasks if item.id == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="Coding task not found")
    return task


@router.get("/coding/tasks", response_model=list[CodingTaskSummary])
def list_coding_tasks() -> list[CodingTaskSummary]:
    return [
        CodingTaskSummary.from_task(task)
        for task in CodingTaskLoader.load_directory(CODING_BENCHMARK_DIRECTORY)
    ]


@router.get("/coding/tasks/{task_id}", response_model=CodingTaskSummary)
def get_coding_task(task_id: str) -> CodingTaskSummary:
    return CodingTaskSummary.from_task(_find_coding_task(task_id))


@router.post("/coding/run", response_model=SafeCodingBenchmarkResponse)
def run_coding_benchmark(
    request: CodingBenchmarkRequest,
) -> SafeCodingBenchmarkResponse:
    task = _find_coding_task(request.task_id)
    try:
        adapter = create_coding_llm_adapter(request.provider, request.model)
        factory = CodingStrategyFactory(
            adapter,
            max_iterations=request.max_iterations,
        )
        runner = CodingBenchmarkRunner(
            factory.direct,
            factory.planner_executor,
            factory.reviewer,
            CodingMetricsCollector(),
            keep_workspaces=request.keep_workspaces,
        )
        result = runner.run_task(task, request.strategies)
    except Exception as exception:
        raise HTTPException(
            status_code=500,
            detail="Coding benchmark environment setup failed",
        ) from exception
    return SafeCodingBenchmarkResponse.from_result(result)
