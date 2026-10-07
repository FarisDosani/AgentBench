import json

import pytest
from pydantic import ValidationError

from app.models.benchmark import BenchmarkRunResult, BenchmarkTaskResult
from app.models.evaluation import EvaluationResult
from app.models.result import AgentRunResult
from app.services.result_store import ResultStore


def make_benchmark_result(agent_name: str = "Test Agent") -> BenchmarkRunResult:
    run_result = AgentRunResult(
        agent_name=agent_name,
        task_id="task-1",
        output="correct",
        success=True,
        latency_ms=12.5,
    )
    evaluation = EvaluationResult(
        task_id="task-1",
        agent_name=agent_name,
        score=1.0,
        passed=True,
    )
    return BenchmarkRunResult(
        agent_name=agent_name,
        total_tasks=1,
        passed_tasks=1,
        failed_tasks=0,
        average_score=1.0,
        average_latency_ms=12.5,
        results=[
            BenchmarkTaskResult(
                run_result=run_result,
                evaluation=evaluation,
            )
        ],
    )


def test_save_creates_directory_and_valid_json_file(tmp_path) -> None:
    results_directory = tmp_path / "nested" / "results"
    store = ResultStore(results_directory)

    saved_path = store.save(make_benchmark_result())

    assert results_directory.is_dir()
    assert saved_path.exists()
    assert saved_path.suffix == ".json"
    assert json.loads(saved_path.read_text(encoding="utf-8"))["agent_name"] == "Test Agent"


def test_load_recreates_matching_benchmark_result(tmp_path) -> None:
    store = ResultStore(tmp_path)
    original = make_benchmark_result()
    saved_path = store.save(original)

    loaded = store.load(saved_path)

    assert isinstance(loaded, BenchmarkRunResult)
    assert loaded == original


@pytest.mark.parametrize(
    ("filename", "expected_name"),
    [("custom.json", "custom.json"), ("custom", "custom.json")],
)
def test_custom_filename_supported(
    tmp_path,
    filename: str,
    expected_name: str,
) -> None:
    saved_path = ResultStore(tmp_path).save(make_benchmark_result(), filename)

    assert saved_path.name == expected_name
    assert saved_path.exists()


def test_generated_filename_contains_sanitized_agent_name(tmp_path) -> None:
    saved_path = ResultStore(tmp_path).save(
        make_benchmark_result("My Agent! Version 2")
    )

    assert saved_path.name.startswith("my_agent_version_2_")
    assert saved_path.name.endswith(".json")
    assert ":" not in saved_path.name


def test_list_results_returns_only_sorted_json_files(tmp_path) -> None:
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    listed = ResultStore(tmp_path).list_results()

    assert [path.name for path in listed] == ["a.json", "b.json"]


def test_list_results_creates_missing_directory(tmp_path) -> None:
    results_directory = tmp_path / "missing"

    assert ResultStore(results_directory).list_results() == []
    assert results_directory.is_dir()


def test_missing_file_raises_file_not_found(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        ResultStore.load(tmp_path / "missing.json")


def test_invalid_json_propagates_decode_error(tmp_path) -> None:
    result_file = tmp_path / "invalid.json"
    result_file.write_text("{invalid", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        ResultStore.load(result_file)


def test_invalid_stored_model_raises_validation_error(tmp_path) -> None:
    result_file = tmp_path / "invalid-model.json"
    result_file.write_text(json.dumps({"agent_name": "Agent"}), encoding="utf-8")

    with pytest.raises(ValidationError):
        ResultStore.load(result_file)
