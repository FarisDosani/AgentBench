from collections.abc import Callable
from typing import Any


Tool = Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Tool name must not be empty")
        return name.strip()

    def register(self, name: str, tool: Tool) -> None:
        validated_name = self._validate_name(name)
        if not callable(tool):
            raise TypeError("Tool must be callable")
        if validated_name in self._tools:
            raise ValueError(f"Tool already registered: {validated_name}")
        self._tools[validated_name] = tool

    def get(self, name: str) -> Tool:
        validated_name = self._validate_name(name)
        if validated_name not in self._tools:
            raise KeyError(validated_name)
        return self._tools[validated_name]

    def has(self, name: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            return False
        return name.strip() in self._tools

    def names(self) -> list[str]:
        return list(self._tools)
