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
    ) -> None:
        self.base_url = (base_url or settings.OMNIROUTE_BASE_URL).rstrip("/")
        self.api_key = settings.OMNIROUTE_API_KEY if api_key is None else api_key
        self.client = httpx.Client()

    def __call__(self, agent: AgentConfig, task: BenchmarkTask) -> str:
        messages: list[dict[str, str]] = []
        if agent.system_prompt is not None:
            messages.append({"role": "system", "content": agent.system_prompt})
        messages.append({"role": "user", "content": task.input})

        payload: dict[str, Any] = {
            "model": agent.model,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "messages": messages,
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
        response_data = response.json()

        choices = response_data.get("choices")
        if not choices:
            raise ValueError("Response choices are missing or empty")

        message = choices[0].get("message")
        if not isinstance(message, dict) or message.get("content") is None:
            raise ValueError("Response message content is missing")

        return str(message["content"])
