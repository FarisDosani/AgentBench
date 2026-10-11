import pytest

from app.services.tool_executor import ToolExecutor
from app.services.tool_registry import ToolRegistry


def test_register_and_retrieve_tool() -> None:
    registry = ToolRegistry()

    def fake_tool() -> str:
        return "result"

    registry.register("fake", fake_tool)

    assert registry.get("fake") is fake_tool
    assert registry.has("fake") is True
    assert registry.has("missing") is False
    assert registry.names() == ["fake"]


def test_duplicate_registration_rejected() -> None:
    registry = ToolRegistry()
    registry.register("fake", lambda: None)

    with pytest.raises(ValueError):
        registry.register("fake", lambda: None)


def test_empty_name_rejected() -> None:
    registry = ToolRegistry()

    with pytest.raises(ValueError):
        registry.register("   ", lambda: None)


def test_successful_tool_execution_passes_kwargs_and_converts_output() -> None:
    registry = ToolRegistry()
    received: dict[str, int] = {}

    def fake_tool(left: int, right: int) -> int:
        received.update(left=left, right=right)
        return left + right

    registry.register("fake", fake_tool)
    result = ToolExecutor(registry).execute("fake", left=2, right=3)

    assert received == {"left": 2, "right": 3}
    assert result.success is True
    assert result.output == "5"
    assert result.error is None
    assert result.latency_ms >= 0


def test_tool_exception_is_captured() -> None:
    registry = ToolRegistry()

    def failing_tool() -> str:
        raise RuntimeError("tool failed")

    registry.register("failing", failing_tool)
    result = ToolExecutor(registry).execute("failing")

    assert result.success is False
    assert result.output is None
    assert result.error == "tool failed"
    assert result.latency_ms >= 0


def test_unknown_tool_returns_failed_result() -> None:
    result = ToolExecutor(ToolRegistry()).execute("missing")

    assert result.tool_name == "missing"
    assert result.success is False
    assert result.output is None
    assert result.error is not None
    assert result.latency_ms >= 0
