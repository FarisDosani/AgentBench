from typing import Protocol

from app.services.gemini_executor import GeminiExecutor
from app.services.omniroute_executor import OmniRouteExecutor


class MessageCompletionProvider(Protocol):
    def complete_messages(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str: ...


class CodingLLMAdapter:
    def __init__(
        self,
        provider: MessageCompletionProvider,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def __call__(self, messages: list[dict[str, str]]) -> str:
        return self.provider.complete_messages(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


def create_coding_llm_adapter(provider: str, model: str) -> CodingLLMAdapter:
    if provider == "gemini":
        executor: MessageCompletionProvider = GeminiExecutor()
    elif provider == "omniroute":
        executor = OmniRouteExecutor()
    else:
        raise ValueError(f"Unsupported coding provider: {provider}")
    return CodingLLMAdapter(executor, model)
