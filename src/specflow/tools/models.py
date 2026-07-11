"""Tool Framework models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from specflow.tools.exceptions import ToolValidationError
from specflow.tools.sanitization import sanitize_json_value, sanitize_mapping, sanitize_tool_text

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){2}$")


class ToolStatus(StrEnum):
    """Tool execution status."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolMetadata:
    """Stable, serializable Tool metadata."""

    name: str
    version: str
    description: str
    input_model: str
    output_model: str
    deterministic: bool
    read_only: bool

    def __post_init__(self) -> None:
        _validate_tool_name(self.name)
        if not isinstance(self.version, str) or not _VERSION_RE.fullmatch(self.version):
            raise ToolValidationError("ToolMetadata.version must use explicit semantic format")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ToolValidationError("ToolMetadata.description must not be empty")
        if not isinstance(self.input_model, str) or not self.input_model.strip():
            raise ToolValidationError("ToolMetadata.input_model must not be empty")
        if not isinstance(self.output_model, str) or not self.output_model.strip():
            raise ToolValidationError("ToolMetadata.output_model must not be empty")
        if not isinstance(self.deterministic, bool) or not isinstance(self.read_only, bool):
            raise ToolValidationError("ToolMetadata flags must be booleans")

    def as_dict(self) -> dict[str, object]:
        """Return a stable serializable representation."""
        return {
            "description": sanitize_tool_text(self.description),
            "deterministic": self.deterministic,
            "input_model": sanitize_tool_text(self.input_model),
            "name": self.name,
            "output_model": sanitize_tool_text(self.output_model),
            "read_only": self.read_only,
            "version": self.version,
        }


@dataclass(frozen=True)
class ToolCall:
    """A structured request to execute a registered Tool."""

    call_id: str
    tool_name: str
    arguments: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    metadata: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ToolValidationError("ToolCall.call_id must not be empty")
        _validate_tool_name(self.tool_name)
        if not isinstance(self.arguments, MappingProxyType):
            object.__setattr__(
                self,
                "arguments",
                MappingProxyType(_normalize_json_mapping(self.arguments)),
            )
        else:
            object.__setattr__(
                self,
                "arguments",
                MappingProxyType(_normalize_json_mapping(dict(self.arguments))),
            )
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", sanitize_mapping(dict(self.metadata)))
        else:
            object.__setattr__(self, "metadata", sanitize_mapping(dict(self.metadata)))

    @classmethod
    def build(
        cls,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ToolCall:
        """Build a ToolCall from mutable input values."""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            arguments=MappingProxyType(dict(arguments or {})),
            metadata=MappingProxyType(dict(metadata or {})),
        )

    def canonical_json(self) -> str:
        """Return stable JSON for tracing and equality checks."""
        payload = {
            "arguments": dict(self.arguments),
            "call_id": self.call_id,
            "metadata": dict(sorted(self.metadata.items())),
            "tool_name": self.tool_name,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ToolResult:
    """Structured result returned by the ToolExecutor."""

    call_id: str
    tool_name: str
    status: ToolStatus
    output: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    metadata: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))
    error_type: str | None = None
    error_message: str | None = None
    requires_review: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ToolValidationError("ToolResult.call_id must not be empty")
        _validate_tool_name(self.tool_name)
        if not isinstance(self.status, ToolStatus):
            raise ToolValidationError("ToolResult.status must be a ToolStatus")
        if not isinstance(self.output, MappingProxyType):
            object.__setattr__(
                self, "output", MappingProxyType(_normalize_json_mapping(self.output))
            )
        else:
            object.__setattr__(
                self,
                "output",
                MappingProxyType(_normalize_json_mapping(dict(self.output))),
            )
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", sanitize_mapping(dict(self.metadata)))
        else:
            object.__setattr__(self, "metadata", sanitize_mapping(dict(self.metadata)))
        if not isinstance(self.requires_review, bool):
            raise ToolValidationError("ToolResult.requires_review must be a bool")
        if self.status == ToolStatus.SUCCESS and (
            self.error_type or self.error_message or self.requires_review
        ):
            raise ToolValidationError("Successful ToolResult must not carry error fields")
        if self.status == ToolStatus.FAILED and not self.error_message:
            raise ToolValidationError("Failed ToolResult must include error_message")
        if self.error_message is not None:
            object.__setattr__(self, "error_message", sanitize_tool_text(self.error_message))

    @classmethod
    def success(
        cls,
        *,
        call_id: str,
        tool_name: str,
        output: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ToolResult:
        """Build a successful ToolResult."""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            status=ToolStatus.SUCCESS,
            output=MappingProxyType(dict(output or {})),
            metadata=MappingProxyType(dict(metadata or {})),
        )

    @classmethod
    def failed(
        cls,
        *,
        call_id: str,
        tool_name: str,
        error_type: str,
        error_message: str,
        requires_review: bool = True,
        metadata: dict[str, str] | None = None,
    ) -> ToolResult:
        """Build a failed ToolResult."""
        return cls(
            call_id=call_id,
            tool_name=tool_name,
            status=ToolStatus.FAILED,
            metadata=MappingProxyType(dict(metadata or {})),
            error_type=error_type,
            error_message=error_message,
            requires_review=requires_review,
        )


def _validate_tool_name(name: str) -> None:
    if not isinstance(name, str) or not _TOOL_NAME_RE.fullmatch(name):
        raise ToolValidationError("Tool name must match ^[a-z][a-z0-9_]*$")


def _normalize_json_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolValidationError("Tool mapping fields must be dict-like")
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ToolValidationError("Tool mapping keys must be non-empty strings")
        try:
            normalized[sanitize_tool_text(key)] = sanitize_json_value(item)
        except TypeError as exc:
            raise ToolValidationError(str(exc)) from exc
    return dict(sorted(normalized.items()))
