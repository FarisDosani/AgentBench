from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.agent import AgentConfig
from app.models.benchmark import BenchmarkRunResult
from app.models.comparison import ComparisonResult
from app.models.task import BenchmarkTask
from app.services.benchmark_runner import BenchmarkRunner
from app.services.comparison_service import ComparisonService
from app.services.evaluator import ExactMatchEvaluator
from app.services.omniroute_executor import OmniRouteExecutor
from app.services.result_store import ResultStore
from app.services.runner import AgentRunner
from app.services.task_loader import TaskLoader


router = APIRouter(prefix="/api")


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
