from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.models.coding_benchmark_run import (
    CodingBenchmarkRunResult,
    StrategyBenchmarkResult,
)
from app.models.coding_metrics import CodingMetrics, FailureCategory
from app.models.coding_task import CodingTask
from app.models.test_result import CodingTestResult, TestCommandResult as CommandResult


client = TestClient(app)


def make_task(tmp_path: Path) -> CodingTask:
    repository = tmp_path / "repo"
    repository.mkdir(exist_ok=True)
    return CodingTask(
        id="coding-task",
        name="Coding task",
        description="Fix behavior.",
        repository_path=str(repository),
        difficulty="medium",
        visible_test_command="pytest tests",
        hidden_test_command="pytest hidden-secret",
        expected_files_changed=["source.py"],
        metadata={"category": "test"},
    )


def make_result() -> CodingBenchmarkRunResult:
    hidden = CommandResult(
        command="pytest hidden-secret",
        exit_code=0,
        stdout="SECRET HIDDEN OUTPUT",
        stderr="SECRET HIDDEN ERROR",
        passed=True,
        timed_out=False,
        duration_ms=1,
    )
    visible = CommandResult(
        command="pytest tests",
        exit_code=0,
        stdout="visible",
        stderr="",
        passed=True,
        timed_out=False,
        duration_ms=1,
    )
    tests = CodingTestResult(
        visible=visible,
        hidden=hidden,
        visible_passed=True,
        hidden_passed=True,
        all_passed=True,
        regression_detected=False,
    )
    metrics = CodingMetrics(
        task_success=True,
        regression_detected=False,
        tool_calls=1,
        runtime_ms=3,
        files_changed=1,
        lines_added=1,
        lines_removed=0,
        patch_size=1,
        failure_category=FailureCategory.NONE,
    )
    return CodingBenchmarkRunResult(
        task_id="coding-task",
        difficulty="medium",
        strategy_results=[
            StrategyBenchmarkResult(
                strategy_name="direct",
                task_id="coding-task",
                success=True,
                test_result=tests,
                metrics=metrics,
                workspace_path="C:/internal/secret",
                error="internal secret should not appear",
            )
        ],
        best_strategy="direct",
    )


def install_api_fakes(monkeypatch, tmp_path: Path):
    captured = {}
    task = make_task(tmp_path)
    monkeypatch.setattr(routes.CodingTaskLoader, "load_directory", lambda path: [task])

    def adapter(provider: str, model: str):
        captured["provider"] = provider
        captured["model"] = model
        return object()

    class Factory:
        def __init__(self, llm, max_iterations):
            captured["max_iterations"] = max_iterations
            self.direct = object()
            self.planner_executor = object()
            self.reviewer = object()

    class Runner:
        def __init__(self, *args, **kwargs):
            captured["keep_workspaces"] = kwargs["keep_workspaces"]

        def run_task(self, task, strategies):
            captured["strategies"] = strategies
            return make_result()

    monkeypatch.setattr(routes, "create_coding_llm_adapter", adapter)
    monkeypatch.setattr(routes, "CodingStrategyFactory", Factory)
    monkeypatch.setattr(routes, "CodingBenchmarkRunner", Runner)
    return captured


def test_list_and_get_coding_tasks_are_safe(tmp_path: Path, monkeypatch) -> None:
    install_api_fakes(monkeypatch, tmp_path)
    listed = client.get("/api/coding/tasks")
    fetched = client.get("/api/coding/tasks/coding-task")

    assert listed.status_code == 200
    assert fetched.status_code == 200
    for payload in [listed.json()[0], fetched.json()]:
        assert payload["id"] == "coding-task"
        assert "hidden_test_command" not in payload
        assert "repository_path" not in payload


def test_missing_coding_task_returns_404(tmp_path: Path, monkeypatch) -> None:
    install_api_fakes(monkeypatch, tmp_path)
    assert client.get("/api/coding/tasks/missing").status_code == 404


def test_coding_run_selects_provider_strategies_and_returns_safe_response(
    tmp_path: Path, monkeypatch
) -> None:
    captured = install_api_fakes(monkeypatch, tmp_path)
    response = client.post(
        "/api/coding/run",
        json={
            "task_id": "coding-task",
            "provider": "omniroute",
            "model": "model-x",
            "strategies": ["reviewer", "direct"],
            "max_iterations": 8,
            "keep_workspaces": True,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "provider": "omniroute",
        "model": "model-x",
        "max_iterations": 8,
        "keep_workspaces": True,
        "strategies": ["reviewer", "direct"],
    }
    body_text = response.text
    assert response.json()["best_strategy"] == "direct"
    assert response.json()["strategy_results"][0]["test_summary"]["hidden_passed"] is True
    for forbidden in [
        "SECRET HIDDEN OUTPUT",
        "SECRET HIDDEN ERROR",
        "hidden-secret",
        "workspace_path",
        "C:/internal/secret",
        "internal secret should not appear",
        "api_key",
    ]:
        assert forbidden not in body_text


def test_default_provider_and_invalid_request_validation(tmp_path: Path, monkeypatch) -> None:
    captured = install_api_fakes(monkeypatch, tmp_path)
    response = client.post(
        "/api/coding/run",
        json={"task_id": "coding-task", "model": "model-x"},
    )
    assert response.status_code == 200
    assert captured["provider"] == "gemini"
    assert captured["strategies"] is None

    invalid_provider = client.post(
        "/api/coding/run",
        json={"task_id": "coding-task", "model": "m", "provider": "invalid"},
    )
    invalid_strategy = client.post(
        "/api/coding/run",
        json={"task_id": "coding-task", "model": "m", "strategies": ["invalid"]},
    )
    assert invalid_provider.status_code == 422
    assert invalid_strategy.status_code == 422


def test_existing_generic_endpoints_still_work() -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/").json() == {"message": "AgentBench"}
