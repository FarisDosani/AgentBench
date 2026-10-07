from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask
from app.services.omniroute_executor import OmniRouteExecutor


def make_agent(system_prompt: str | None = "Follow instructions.") -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        model="test-model",
        system_prompt=system_prompt,
        temperature=0.4,
        max_tokens=256,
    )


def make_task() -> BenchmarkTask:
    return BenchmarkTask(
        id="task-1",
        name="Test task",
        description="A test task.",
        input="Answer this input.",
    )


def make_executor(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str = "",
) -> OmniRouteExecutor:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "app.services.omniroute_executor.httpx.Client",
        lambda: client,
    )
    return OmniRouteExecutor(base_url="http://localhost:20128/v1", api_key=api_key)


def test_request_and_response_with_system_prompt_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "model output"}}]},
        )

    executor = make_executor(monkeypatch, handler, api_key="test-key")
    output = executor(make_agent(), make_task())

    assert captured["url"] == "http://localhost:20128/v1/chat/completions"
    assert captured["json"] == {
        "model": "test-model",
        "temperature": 0.4,
        "max_tokens": 256,
        "messages": [
            {"role": "system", "content": "Follow instructions."},
            {"role": "user", "content": "Answer this input."},
        ],
    }
    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert captured["headers"]["content-type"] == "application/json"
    assert output == "model output"


def test_system_prompt_and_authorization_omitted_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "output"}}]},
        )

    executor = make_executor(monkeypatch, handler)
    executor(make_agent(system_prompt=None), make_task())

    assert captured["json"]["messages"] == [
        {"role": "user", "content": "Answer this input."}
    ]
    assert "authorization" not in captured["headers"]


def test_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(500, json={"error": "failed"}),
    )

    with pytest.raises(httpx.HTTPStatusError):
        executor(make_agent(), make_task())


@pytest.mark.parametrize("response_json", [{}, {"choices": []}])
def test_missing_or_empty_choices_rejected(
    monkeypatch: pytest.MonkeyPatch,
    response_json: dict[str, Any],
) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(200, json=response_json),
    )

    with pytest.raises(ValueError, match="choices"):
        executor(make_agent(), make_task())


@pytest.mark.parametrize(
    "response_json",
    [
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
    ],
)
def test_missing_content_rejected(
    monkeypatch: pytest.MonkeyPatch,
    response_json: dict[str, Any],
) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(200, json=response_json),
    )

    with pytest.raises(ValueError, match="content"):
        executor(make_agent(), make_task())
