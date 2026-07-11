"""Tool Executor for one explicit ToolCall."""

from __future__ import annotations

from specflow.tools.exceptions import ToolExecutionError, ToolNotFoundError
from specflow.tools.models import ToolCall, ToolResult, ToolStatus
from specflow.tools.registry import ToolRegistry
from specflow.tools.sanitization import sanitize_tool_text


class ToolExecutor:
    """Execute exactly one registered Tool per call."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, call: ToolCall) -> ToolResult:
        """Execute one ToolCall through the registry."""
        if not isinstance(call, ToolCall):
            raise ToolExecutionError("ToolExecutor.execute requires a ToolCall")
        try:
            tool = self._registry.get(call.tool_name)
        except ToolNotFoundError as exc:
            return ToolResult.failed(
                call_id=call.call_id,
                tool_name=call.tool_name,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        try:
            result = tool.execute(call)
            if not isinstance(result, ToolResult):
                raise ToolExecutionError("Tool.execute must return ToolResult")
            self._validate_result_matches_call(call, result)
            return result
        except Exception as exc:
            return ToolResult.failed(
                call_id=call.call_id,
                tool_name=call.tool_name,
                error_type=type(exc).__name__,
                error_message=sanitize_tool_text(str(exc)),
            )

    @staticmethod
    def _validate_result_matches_call(call: ToolCall, result: ToolResult) -> None:
        if result.call_id != call.call_id:
            raise ToolExecutionError("ToolResult.call_id must match ToolCall.call_id")
        if result.tool_name != call.tool_name:
            raise ToolExecutionError("ToolResult.tool_name must match ToolCall.tool_name")
        if result.status not in {ToolStatus.SUCCESS, ToolStatus.FAILED}:
            raise ToolExecutionError("ToolResult.status is invalid")
