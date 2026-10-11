from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent

BENCHMARK_DIRECTORY = BACKEND_ROOT / "benchmarks"
CODING_BENCHMARK_DIRECTORY = BACKEND_ROOT / "coding_benchmarks"
RESULTS_DIRECTORY = REPOSITORY_ROOT / "results"
