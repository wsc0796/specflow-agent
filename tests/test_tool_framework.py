import pytest

from specflow.tools import (
    DuplicateToolError,
    ToolCall,
    ToolExecutor,
    ToolMetadata,
    ToolNotFoundError,
    ToolRegistry,
    ToolResult,
    ToolStatus,
    ToolValidationError,
)
from specflow.tools.exceptions import ToolExecutionError


class FakeEchoTool:
    def __init__(self, name: str = "fake_echo") -> None:
        self.calls = 0
        self._metadata = ToolMetadata(
            name=name,
            version="1.0.0",
            description="Echo structured test arguments.",
            input_model="FakeEchoInput",
            output_model="FakeEchoOutput",
            deterministic=True,
            read_only=True,
        )

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    def execute(self, call: ToolCall) -> ToolResult:
        self.calls += 1
        return ToolResult.success(
            call_id=call.call_id,
            tool_name=call.tool_name,
            output={"echo": dict(call.arguments)},
            metadata={"source": "fake"},
        )


class FakeFailureTool(FakeEchoTool):
    def __init__(self) -> None:
        super().__init__("fake_failure")

    def execute(self, call: ToolCall) -> ToolResult:
        self.calls += 1
        raise RuntimeError("api_key=sk-abc123def456ghi789jkl012 password=hunter2")


class FakeInvalidResultTool(FakeEchoTool):
    def __init__(self) -> None:
        super().__init__("fake_invalid")

    def execute(self, call: ToolCall):
        self.calls += 1
        return {"not": "tool result"}


class FakeMismatchTool(FakeEchoTool):
    def __init__(self) -> None:
        super().__init__("fake_mismatch")

    def execute(self, call: ToolCall) -> ToolResult:
        self.calls += 1
        return ToolResult.success(call_id="other", tool_name=call.tool_name, output={})


def _call(tool_name: str = "fake_echo") -> ToolCall:
    return ToolCall.build(
        call_id="call-001",
        tool_name=tool_name,
        arguments={"message": "hello", "count": 1},
        metadata={"request_id": "req-001"},
    )


def test_valid_tool_metadata() -> None:
    metadata = FakeEchoTool().metadata

    assert metadata.as_dict()["name"] == "fake_echo"
    assert metadata.deterministic
    assert metadata.read_only


def test_empty_tool_name_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        ToolMetadata(
            name="",
            version="1.0.0",
            description="desc",
            input_model="Input",
            output_model="Output",
            deterministic=True,
            read_only=True,
        )


def test_invalid_tool_name_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        FakeEchoTool("Fake-Echo").metadata


def test_empty_version_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        ToolMetadata(
            name="fake_echo",
            version="",
            description="desc",
            input_model="Input",
            output_model="Output",
            deterministic=True,
            read_only=True,
        )


def test_empty_description_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        ToolMetadata(
            name="fake_echo",
            version="1.0.0",
            description=" ",
            input_model="Input",
            output_model="Output",
            deterministic=True,
            read_only=True,
        )


def test_valid_tool_call() -> None:
    call = _call()

    assert call.call_id == "call-001"
    assert call.tool_name == "fake_echo"
    assert call.arguments["message"] == "hello"


def test_empty_call_id_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        ToolCall.build(call_id="", tool_name="fake_echo")


def test_tool_call_arguments_are_stably_copied() -> None:
    args = {"b": 2, "a": {"token": "raw-secret"}}

    call = ToolCall.build(call_id="call-001", tool_name="fake_echo", arguments=args)
    args["b"] = 3

    assert call.arguments["b"] == 2
    assert call.canonical_json() == call.canonical_json()
    assert "raw-secret" not in call.canonical_json()


def test_tool_result_success_contract() -> None:
    result = ToolResult.success(
        call_id="call-001",
        tool_name="fake_echo",
        output={"value": "ok"},
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.output["value"] == "ok"


def test_tool_result_failed_contract() -> None:
    result = ToolResult.failed(
        call_id="call-001",
        tool_name="fake_echo",
        error_type="RuntimeError",
        error_message="boom",
    )

    assert result.status == ToolStatus.FAILED
    assert result.requires_review


def test_success_with_error_fields_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        ToolResult(
            call_id="call-001",
            tool_name="fake_echo",
            status=ToolStatus.SUCCESS,
            error_type="RuntimeError",
            error_message="boom",
        )


def test_failed_without_error_message_is_rejected() -> None:
    with pytest.raises(ToolValidationError):
        ToolResult(
            call_id="call-001",
            tool_name="fake_echo",
            status=ToolStatus.FAILED,
        )


def test_registry_registers_tool() -> None:
    registry = ToolRegistry()
    tool = FakeEchoTool()

    registry.register(tool)

    assert registry.has("fake_echo")


def test_registry_gets_tool() -> None:
    registry = ToolRegistry()
    tool = FakeEchoTool()
    registry.register(tool)

    assert registry.get("fake_echo") is tool


def test_duplicate_tool_name_is_rejected() -> None:
    registry = ToolRegistry()
    registry.register(FakeEchoTool())

    with pytest.raises(DuplicateToolError):
        registry.register(FakeEchoTool())


def test_missing_tool_lookup_fails() -> None:
    with pytest.raises(ToolNotFoundError):
        ToolRegistry().get("fake_missing")


def test_metadata_order_is_deterministic() -> None:
    registry = ToolRegistry()
    registry.register(FakeEchoTool("fake_z"))
    registry.register(FakeEchoTool("fake_a"))

    assert [metadata.name for metadata in registry.metadata()] == ["fake_a", "fake_z"]


def test_fake_echo_tool_executes() -> None:
    registry = ToolRegistry()
    registry.register(FakeEchoTool())

    result = ToolExecutor(registry).execute(_call())

    assert result.status == ToolStatus.SUCCESS
    assert result.output["echo"]["message"] == "hello"


def test_fake_failure_tool_converts_to_failed_result() -> None:
    registry = ToolRegistry()
    registry.register(FakeFailureTool())

    result = ToolExecutor(registry).execute(_call("fake_failure"))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "RuntimeError"


def test_invalid_tool_result_fails_clearly() -> None:
    registry = ToolRegistry()
    registry.register(FakeInvalidResultTool())

    result = ToolExecutor(registry).execute(_call("fake_invalid"))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "ToolExecutionError"


def test_tool_result_call_id_matches_call() -> None:
    result = ToolExecutor(_registry_with_echo()).execute(_call())

    assert result.call_id == "call-001"


def test_tool_result_tool_name_matches_call() -> None:
    result = ToolExecutor(_registry_with_echo()).execute(_call())

    assert result.tool_name == "fake_echo"


def test_same_call_executes_target_once() -> None:
    registry = ToolRegistry()
    tool = FakeEchoTool()
    registry.register(tool)

    ToolExecutor(registry).execute(_call())

    assert tool.calls == 1


def test_unregistered_tool_is_not_executed() -> None:
    tool = FakeEchoTool()

    result = ToolExecutor(ToolRegistry()).execute(_call("fake_echo"))

    assert result.status == ToolStatus.FAILED
    assert tool.calls == 0


def test_plain_callable_cannot_bypass_registry() -> None:
    executor = ToolExecutor(_registry_with_echo())

    with pytest.raises(ToolExecutionError):
        executor.execute(lambda: "nope")  # type: ignore[arg-type]


def test_sensitive_error_message_is_redacted() -> None:
    registry = ToolRegistry()
    registry.register(FakeFailureTool())

    result = ToolExecutor(registry).execute(_call("fake_failure"))

    assert "sk-abc123" not in result.error_message
    assert "hunter2" not in result.error_message
    assert "api_key=<redacted>" in result.error_message
    assert "password=<redacted>" in result.error_message


def test_registry_is_not_global_singleton() -> None:
    first = ToolRegistry()
    second = ToolRegistry()
    first.register(FakeEchoTool())

    assert first.has("fake_echo")
    assert not second.has("fake_echo")


def test_registration_order_does_not_affect_metadata() -> None:
    first = ToolRegistry()
    first.register(FakeEchoTool("fake_b"))
    first.register(FakeEchoTool("fake_a"))
    second = ToolRegistry()
    second.register(FakeEchoTool("fake_a"))
    second.register(FakeEchoTool("fake_b"))

    assert first.metadata() == second.metadata()


def test_mismatched_tool_result_is_failed() -> None:
    registry = ToolRegistry()
    registry.register(FakeMismatchTool())

    result = ToolExecutor(registry).execute(_call("fake_mismatch"))

    assert result.status == ToolStatus.FAILED
    assert result.error_type == "ToolExecutionError"


def _registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    return registry
