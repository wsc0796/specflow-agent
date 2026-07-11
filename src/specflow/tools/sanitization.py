"""Sensitive information sanitization for Tool Framework."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from specflow.context import _redact_secrets, _strip_control

_BEARER_RE = re.compile(r"bearer\s+[a-zA-Z0-9._~+/=-]+", re.IGNORECASE)
_AUTHORIZATION_RE = re.compile(r"authorization[=:]\s*\S+", re.IGNORECASE)
_ACCESS_TOKEN_RE = re.compile(r"access_token[=:]\s*\S+", re.IGNORECASE)
_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|access[_-]?token|authorization|password|secret|token)",
    re.IGNORECASE,
)
_JSON_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_tool_text(text: str) -> str:
    """Redact common credential patterns and strip control characters."""
    cleaned = _strip_control(_redact_tool_secrets(text))
    return cleaned


def sanitize_json_text(text: str) -> str:
    """Redact JSON string values while retaining meaningful line structure."""
    return _JSON_CONTROL_RE.sub("", _redact_tool_secrets(text))


def _redact_tool_secrets(text: str) -> str:
    cleaned = _redact_secrets(text)
    cleaned = _BEARER_RE.sub("Bearer <redacted>", cleaned)
    cleaned = _AUTHORIZATION_RE.sub("authorization=<redacted>", cleaned)
    cleaned = _ACCESS_TOKEN_RE.sub("access_token=<redacted>", cleaned)
    return cleaned


def sanitize_mapping(mapping: Mapping[str, str]) -> MappingProxyType[str, str]:
    """Return immutable sanitized string metadata."""
    return MappingProxyType(
        {
            sanitize_tool_text(str(key)): _sanitize_value_for_key(str(key), str(value))
            for key, value in mapping.items()
        }
    )


def sanitize_json_value(value: Any) -> Any:
    """Recursively sanitize JSON-like values while preserving structure."""
    if isinstance(value, str):
        return sanitize_json_text(value)
    if isinstance(value, bool) or value is None or isinstance(value, int | float):
        return value
    if isinstance(value, Mapping):
        return {
            sanitize_tool_text(str(key)): _sanitize_json_value_for_key(str(key), item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, tuple | list):
        return [sanitize_json_value(item) for item in value]
    raise TypeError(f"Unsupported non-serializable value: {type(value).__name__}")


def _sanitize_value_for_key(key: str, value: str) -> str:
    if _SENSITIVE_KEY_RE.search(key):
        return "<redacted>"
    return sanitize_tool_text(value)


def _sanitize_json_value_for_key(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY_RE.search(key):
        return "<redacted>"
    return sanitize_json_value(value)
