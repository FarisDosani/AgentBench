from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.models.agent import AgentConfig
from app.models.benchmark import BenchmarkRunResult
from app.models.task import BenchmarkTask
from app.services.result_store import ResultStore


client = TestClient(app)


def make_task(task_id: str = "task-1") -> BenchmarkTask:
    return BenchmarkTask(
        id=task_id,
        name="API task",
        description="A task used by API tests.",
        input="Return expected.",
        expected_output="expected",
    )


def make_run(
    agent_name: str = "api-agent",
    score: float = 1.0,
    latency: float = 10.0,
) -> BenchmarkRunResult:
    passed = 1 if score == 1.0 else 0
    return BenchmarkRunResult(
        agent_name=agent_name,
        total_tasks=1,
        passed_tasks=passed,
        failed_tasks=1 - passed,
        average_score=score,
        average_latency_ms=latency,
        results=[],
    )


@pytest.fixture
def temporary_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ResultStore:
    store = ResultStore(tmp_path / "results")
    monkeypatch.setattr(routes, "ResultStore", lambda: store)
    return store


def test_get_tasks_returns_task_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routes.TaskLoader,
        "load_directory",
        lambda path: [make_task()],
    )

    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "task-1"


def test_list_results_returns_filenames_only(temporary_store: ResultStore) -> None:
    temporary_store.save(make_run("b-agent"), "b.json")
    temporary_store.save(make_run("a-agent"), "a.json")
    (temporary_store.directory / "notes.txt").write_text("ignored", encoding="utf-8")

    response = client.get("/api/results")

    assert response.status_code == 200
    assert response.json() == ["a.json", "b.json"]


def test_get_saved_result(temporary_store: ResultStore) -> None:
    temporary_store.save(make_run(), "saved.json")

    response = client.get("/api/results/saved.json")

    assert response.status_code == 200
    assert response.json()["agent_name"] == "api-agent"


def test_missing_result_returns_404(temporary_store: ResultStore) -> None:
    response = client.get("/api/results/missing.json")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "filename",
    ["bad..name.json", "folder%5Cresult.json"],
)
def test_invalid_or_traversal_result_filename_rejected(
    temporary_store: ResultStore,
    filename: str,
) -> None:
    response = client.get(f"/api/results/{filename}")

    assert response.status_code == 400


def test_non_json_result_filename_rejected(temporary_store: ResultStore) -> None:
    response = client.get("/api/results/result.txt")

    assert response.status_code == 400


def test_compare_returns_comparison(temporary_store: ResultStore) -> None:
    temporary_store.save(make_run("slower", latency=20.0), "slower.json")
    temporary_store.save(make_run("faster", latency=5.0), "faster.json")

    response = client.post("/api/compare", json=["slower.json", "faster.json"])

    assert response.status_code == 200
    assert response.json()["best_agent"] == "faster"
    assert [summary["agent_name"] for summary in response.json()["summaries"]] == [
        "faster",
        "slower",
    ]


def test_missing_comparison_file_returns_404(temporary_store: ResultStore) -> None:
    response = client.post("/api/compare", json=["missing.json"])

    assert response.status_code == 404


def test_run_benchmark_uses_mocked_executor_and_saves_result(
    temporary_store: ResultStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.TaskLoader,
        "load_directory",
        lambda path: [make_task()],
    )

    def fake_executor(agent: AgentConfig, task: BenchmarkTask) -> str:
        return "expected"

    monkeypatch.setattr(routes, "OmniRouteExecutor", lambda: fake_executor)

    response = client.post(
        "/api/benchmarks/run",
        json={"name": "api-agent", "model": "mock-model"},
    )

    assert response.status_code == 200
    assert response.json()["total_tasks"] == 1
    assert response.json()["passed_tasks"] == 1
    assert response.json()["agent_name"] == "api-agent"
    assert len(temporary_store.list_results()) == 1


def test_existing_health_route_still_works() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_existing_root_route_still_works() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "AgentBench"}
