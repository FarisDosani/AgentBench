from collections.abc import Callable
import json
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
        expected_output="EXPECTED_SECRET",
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
        lambda **kwargs: client,
    )
    return OmniRouteExecutor(base_url="http://localhost:20128/v1", api_key=api_key)


def test_configured_timeout_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    original_client = httpx.Client

    def client_factory(**kwargs: Any) -> httpx.Client:
        captured.update(kwargs)
        return original_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        )

    monkeypatch.setattr(
        "app.services.omniroute_executor.settings.OMNIROUTE_TIMEOUT_SECONDS",
        45.0,
    )
    monkeypatch.setattr(
        "app.services.omniroute_executor.httpx.Client",
        client_factory,
    )

    executor = OmniRouteExecutor()

    assert captured["timeout"] == 45.0
    assert executor.timeout_seconds == 45.0


def test_explicit_timeout_override_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    original_client = httpx.Client

    def client_factory(**kwargs: Any) -> httpx.Client:
        captured.update(kwargs)
        return original_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        )

    monkeypatch.setattr(
        "app.services.omniroute_executor.httpx.Client",
        client_factory,
    )

    executor = OmniRouteExecutor(timeout_seconds=12.5)

    assert captured["timeout"] == 12.5
    assert executor.timeout_seconds == 12.5


def test_request_and_response_with_system_prompt_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "model output"}}]},
        )

    executor = make_executor(monkeypatch, handler, api_key="test-key")
    output = executor(make_agent(), make_task())

    assert captured["url"] == "http://localhost:20128/v1/chat/completions"
    user_prompt = captured["json"]["messages"][-1]["content"]
    assert "A test task." in user_prompt
    assert "Answer this input." in user_prompt
    assert "Return only the final answer." in user_prompt
    assert "EXPECTED_SECRET" not in user_prompt
    assert captured["json"] == {
        "model": "test-model",
        "temperature": 0.4,
        "max_tokens": 256,
        "stream": False,
        "messages": [
            {"role": "system", "content": "Follow instructions."},
            {
                "role": "user",
                "content": (
                    "Task:\nA test task.\n\n"
                    "Input:\nAnswer this input.\n\n"
                    "Return only the final answer. Do not include explanation, reasoning, "
                    "markdown, labels, or extra text."
                ),
            },
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
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "output"}}]},
        )

    executor = make_executor(monkeypatch, handler)
    executor(make_agent(system_prompt=None), make_task())

    assert captured["json"]["messages"] == [
        {
            "role": "user",
            "content": (
                "Task:\nA test task.\n\n"
                "Input:\nAnswer this input.\n\n"
                "Return only the final answer. Do not include explanation, reasoning, "
                "markdown, labels, or extra text."
            ),
        }
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


def test_sse_content_chunks_are_combined_and_done_stops_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "\n".join(
        [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            "",
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "",
            "data: [DONE]",
            "data: this would be invalid JSON after completion",
        ]
    )
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(200, text=body),
    )

    assert executor(make_agent(), make_task()) == "Hello world"


def test_sse_role_only_chunks_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    body = "\n".join(
        [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"Answer"}}]}',
            "data: [DONE]",
        ]
    )
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            text=body,
            headers={"Content-Type": "text/event-stream"},
        ),
    )

    assert executor(make_agent(), make_task()) == "Answer"


def test_sse_without_content_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "\n".join(
        [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            "data: [DONE]",
        ]
    )
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            text=body,
            headers={"Content-Type": "text/event-stream"},
        ),
    )

    with pytest.raises(ValueError, match="OmniRoute returned no assistant content"):
        executor(make_agent(), make_task())


def test_malformed_sse_json_propagates_decode_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            text="data: {malformed}\n\ndata: [DONE]",
            headers={"Content-Type": "text/event-stream"},
        ),
    )

    with pytest.raises(json.JSONDecodeError):
        executor(make_agent(), make_task())
