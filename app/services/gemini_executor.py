from typing import Any

import httpx

from app.core.config import settings
from app.models.agent import AgentConfig
from app.models.task import BenchmarkTask


class GeminiExecutor:
    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = settings.GEMINI_API_KEY if api_key is None else api_key
        self.default_model = default_model or settings.GEMINI_MODEL
        self.timeout_seconds = (
            settings.OMNIROUTE_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        )
        self.client = httpx.Client(timeout=self.timeout_seconds)

    def __call__(self, agent: AgentConfig, task: BenchmarkTask) -> str:
        if not self.api_key.strip():
            raise ValueError("Gemini API key is required")

        model = agent.model or self.default_model
        user_prompt = (
            f"Task:\n{task.description}\n\n"
            f"Input:\n{task.input}\n\n"
            "Return only the final answer. Do not include explanation, reasoning, "
            "markdown, labels, or extra text."
        )
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": agent.temperature,
                "maxOutputTokens": agent.max_tokens,
            },
        }
        if agent.system_prompt is not None:
            payload["systemInstruction"] = {
                "parts": [{"text": agent.system_prompt}]
            }

        response = self.client.post(
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{model}:generateContent",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
        )
        response.raise_for_status()
        response_data = response.json()

        candidates = response_data.get("candidates")
        if not candidates:
            raise ValueError("Gemini response candidates are missing or empty")

        content = candidates[0].get("content")
        if not isinstance(content, dict):
            raise ValueError("Gemini response content is missing")

        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ValueError("Gemini response parts are missing or empty")

        text_parts: list[str] = []
        for part in parts:
            if not isinstance(part, dict) or part.get("text") is None:
                raise ValueError("Gemini response text is missing")
            text_parts.append(str(part["text"]))

        text = "".join(text_parts)
        if not text:
            raise ValueError("Gemini response text is missing")
        return text
