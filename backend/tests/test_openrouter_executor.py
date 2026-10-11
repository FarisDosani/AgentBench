import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask
from app.services.openrouter_executor import OpenRouterExecutor


def make_agent(system_prompt: str | None = "Preserve this system prompt.") -> AgentConfig:
    return AgentConfig(
        name="openrouter-agent",
        model="provider/model",
        system_prompt=system_prompt,
        temperature=0.4,
        max_tokens=321,
    )


def make_task() -> BenchmarkTask:
    return BenchmarkTask(
        id="task-1",
        name="OpenRouter task",
        description="Transform the supplied text.",
        input="make this uppercase",
        expected_output="EXPECTED_SECRET",
    )


def make_executor(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str = "test-openrouter-key",
) -> OpenRouterExecutor:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "app.services.openrouter_executor.httpx.Client",
        lambda **kwargs: client,
    )
    return OpenRouterExecutor(
        base_url="https://openrouter.test/api/v1/",
        api_key=api_key,
    )


def test_constructor_uses_config_and_default_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def client(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "app.services.openrouter_executor.settings.OPENROUTER_BASE_URL",
        "https://configured.openrouter.test/v1/",
    )
    monkeypatch.setattr(
        "app.services.openrouter_executor.settings.OPENROUTER_API_KEY",
        "configured-key",
    )
    monkeypatch.setattr("app.services.openrouter_executor.httpx.Client", client)

    executor = OpenRouterExecutor()

    assert executor.base_url == "https://configured.openrouter.test/v1"
    assert executor.api_key == "configured-key"
    assert executor.timeout_seconds == 60.0
    assert captured["timeout"] == 60.0


def test_generic_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "FINAL"}}]},
        )

    output = make_executor(monkeypatch, handler)(make_agent(), make_task())

    assert captured["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-openrouter-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "provider/model"
    assert captured["json"]["temperature"] == 0.4
    assert captured["json"]["max_tokens"] == 321
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"][0] == {
        "role": "system",
        "content": "Preserve this system prompt.",
    }
    user_prompt = captured["json"]["messages"][1]
    assert user_prompt["role"] == "user"
    assert "Task:\nTransform the supplied text." in user_prompt["content"]
    assert "Input:\nmake this uppercase" in user_prompt["content"]
    assert "Return only the final answer." in user_prompt["content"]
    assert "EXPECTED_SECRET" not in user_prompt["content"]
    assert output == "FINAL"


def test_system_prompt_is_omitted_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
        )

    assert make_executor(monkeypatch, handler)(make_agent(None), make_task()) == "answer"
    assert [message["role"] for message in captured["json"]["messages"]] == [
        "user"
    ]


def test_generate_messages_forwards_complete_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "inspect"},
        {"role": "assistant", "content": "tool request"},
        {"role": "user", "content": "tool result"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "next"}}]},
        )

    output = make_executor(monkeypatch, handler).generate_messages(
        messages,
        model="coding/model",
        temperature=0.1,
        max_tokens=777,
    )

    assert output == "next"
    assert captured["json"] == {
        "model": "coding/model",
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 777,
        "stream": False,
    }


def test_missing_key_is_rejected_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_made = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_made
        request_made = True
        return httpx.Response(200)

    executor = make_executor(monkeypatch, handler, api_key="")

    with pytest.raises(ValueError, match="OpenRouter API key"):
        executor(make_agent(), make_task())
    assert request_made is False


def test_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(503, json={"error": "unavailable"}),
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
    "choice",
    [{}, {"message": {}}, {"message": {"content": None}}],
)
def test_missing_content_rejected(
    monkeypatch: pytest.MonkeyPatch,
    choice: dict[str, Any],
) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(200, json={"choices": [choice]}),
    )

    with pytest.raises(ValueError, match="content"):
        executor(make_agent(), make_task())
