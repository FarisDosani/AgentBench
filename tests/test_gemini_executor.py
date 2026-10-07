import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask
from app.services.gemini_executor import GeminiExecutor


def make_agent(system_prompt: str | None = "Preserve this prompt exactly.") -> AgentConfig:
    return AgentConfig(
        name="gemini-agent",
        model="gemini-test-model",
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=512,
    )


def make_task() -> BenchmarkTask:
    return BenchmarkTask(
        id="task-1",
        name="Gemini task",
        description="A task used to test Gemini execution.",
        input="Answer this Gemini task.",
        expected_output="EXPECTED_SECRET",
    )


def make_executor(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str = "test-gemini-key",
) -> GeminiExecutor:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "app.services.gemini_executor.httpx.Client",
        lambda **kwargs: client,
    )
    return GeminiExecutor(api_key=api_key)


def test_request_and_multi_part_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Hello"}, {"text": " world"}]}}
                ]
            },
        )

    output = make_executor(monkeypatch, handler)(make_agent(), make_task())

    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-test-model:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "test-gemini-key"
    user_prompt = captured["json"]["contents"][0]["parts"][0]["text"]
    assert "A task used to test Gemini execution." in user_prompt
    assert "Answer this Gemini task." in user_prompt
    assert "Return only the final answer." in user_prompt
    assert "EXPECTED_SECRET" not in user_prompt
    assert captured["json"] == {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Task:\nA task used to test Gemini execution.\n\n"
                            "Input:\nAnswer this Gemini task.\n\n"
                            "Return only the final answer. Do not include explanation, "
                            "reasoning, markdown, labels, or extra text."
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 512,
        },
        "systemInstruction": {
            "parts": [{"text": "Preserve this prompt exactly."}]
        },
    }
    assert output == "Hello world"


def test_system_instruction_omitted_when_prompt_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Answer"}]}}]},
        )

    output = make_executor(monkeypatch, handler)(make_agent(None), make_task())

    assert "systemInstruction" not in captured["json"]
    assert output == "Answer"


def test_missing_api_key_rejected_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_made = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_made
        request_made = True
        return httpx.Response(200)

    executor = make_executor(monkeypatch, handler, api_key="")

    with pytest.raises(ValueError, match="API key"):
        executor(make_agent(), make_task())
    assert request_made is False


def test_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(401, json={"error": "unauthorized"}),
    )

    with pytest.raises(httpx.HTTPStatusError):
        executor(make_agent(), make_task())


@pytest.mark.parametrize("response_json", [{}, {"candidates": []}])
def test_missing_or_empty_candidates_rejected(
    monkeypatch: pytest.MonkeyPatch,
    response_json: dict[str, Any],
) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(200, json=response_json),
    )

    with pytest.raises(ValueError, match="candidates"):
        executor(make_agent(), make_task())


def test_missing_content_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(200, json={"candidates": [{}]}),
    )

    with pytest.raises(ValueError, match="content"):
        executor(make_agent(), make_task())


@pytest.mark.parametrize(
    "content",
    [{}, {"parts": []}],
)
def test_missing_or_empty_parts_rejected(
    monkeypatch: pytest.MonkeyPatch,
    content: dict[str, Any],
) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"candidates": [{"content": content}]}
        ),
    )

    with pytest.raises(ValueError, match="parts"):
        executor(make_agent(), make_task())


def test_missing_text_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = make_executor(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{}]}}]},
        ),
    )

    with pytest.raises(ValueError, match="text"):
        executor(make_agent(), make_task())
