import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask


class OmniRouteExecutor:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OMNIROUTE_BASE_URL).rstrip("/")
        self.api_key = settings.OMNIROUTE_API_KEY if api_key is None else api_key
        self.timeout_seconds = (
            settings.OMNIROUTE_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        )
        self.client = httpx.Client(timeout=self.timeout_seconds)

    def __call__(self, agent: AgentConfig, task: BenchmarkTask) -> str:
        messages: list[dict[str, str]] = []
        if agent.system_prompt is not None:
            messages.append({"role": "system", "content": agent.system_prompt})
        user_prompt = (
            f"Task:\n{task.description}\n\n"
            f"Input:\n{task.input}\n\n"
            "Return only the final answer. Do not include explanation, reasoning, "
            "markdown, labels, or extra text."
        )
        messages.append({"role": "user", "content": user_prompt})

        payload: dict[str, Any] = {
            "model": agent.model,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "messages": messages,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        response_text = response.text
        if "text/event-stream" in content_type or response_text.startswith("data:"):
            return self._parse_sse(response_text)

        response_data = response.json()

        choices = response_data.get("choices")
        if not choices:
            raise ValueError("Response choices are missing or empty")

        message = choices[0].get("message")
        if not isinstance(message, dict) or message.get("content") is None:
            raise ValueError("Response message content is missing")

        return str(message["content"])

    @staticmethod
    def _parse_sse(response_text: str) -> str:
        content_chunks: list[str] = []

        for line in response_text.splitlines():
            if not line or not line.startswith("data:"):
                continue

            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break

            event = json.loads(data)
            choices = event.get("choices")
            if not choices:
                continue

            delta = choices[0].get("delta")
            if not isinstance(delta, dict):
                continue

            content = delta.get("content")
            if content is not None:
                content_chunks.append(str(content))

        content = "".join(content_chunks)
        if not content:
            raise ValueError("OmniRoute returned no assistant content")
        return content
