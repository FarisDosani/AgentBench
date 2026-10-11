from typing import Any

import httpx

from app.core.config import settings
from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask


class OpenRouterExecutor:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.base_url = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.api_key = settings.OPENROUTER_API_KEY if api_key is None else api_key
        self.timeout_seconds = timeout_seconds
        self.client = httpx.Client(timeout=timeout_seconds)

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
        return self.generate_messages(
            messages,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
        )

    def complete_messages(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        return self.generate_messages(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        if not self.api_key.strip():
            raise ValueError("OpenRouter API key is required")

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        response_data = response.json()

        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("OpenRouter response choices are missing or empty")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("OpenRouter response message content is missing")
        message = first_choice.get("message")
        if not isinstance(message, dict) or message.get("content") is None:
            raise ValueError("OpenRouter response message content is missing")
        return str(message["content"])
