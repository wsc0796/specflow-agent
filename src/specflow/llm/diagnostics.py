"""Bounded response facts that may safely accompany an LLM failure."""

from __future__ import annotations

from dataclasses import dataclass

_FAILURE_PHASES = frozenset(
    {"provider_transport", "response_normalization", "json_parse", "schema_validation"}
)
_FINISH_REASONS = frozenset(
    {
        "stop",
        "length",
        "tool_calls",
        "content_filter",
        "function_call",
        "eos_token",
        "end_turn",
        "max_tokens",
        "stop_sequence",
    }
)


def _known_tokens(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


@dataclass(frozen=True)
class LLMFailureDiagnostics:
    """Retain only allowlisted facts, without response bodies or provider text."""

    phase: str
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    content_empty: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.phase, str) or self.phase not in _FAILURE_PHASES:
            raise ValueError("Invalid LLM failure phase")
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str) or self.finish_reason not in _FINISH_REASONS
        ):
            object.__setattr__(self, "finish_reason", "unknown")
        object.__setattr__(self, "input_tokens", _known_tokens(self.input_tokens))
        object.__setattr__(self, "output_tokens", _known_tokens(self.output_tokens))
        if not isinstance(self.content_empty, bool):
            object.__setattr__(self, "content_empty", None)

    def as_dict(self) -> dict[str, object]:
        known = sum(value is not None for value in (self.input_tokens, self.output_tokens))
        return {
            "failure_stage": self.phase,
            "finish_reason": self.finish_reason,
            "usage": {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens},
            "usage_status": ("unknown", "partial", "known")[known],
            "content_empty": self.content_empty,
            "schema_validation": "failed" if self.phase == "schema_validation" else "not_run",
        }

    @classmethod
    def from_dict(cls, value: object) -> LLMFailureDiagnostics | None:
        """Rebuild an untrusted diagnostic envelope using only safe fields."""
        if not isinstance(value, dict):
            return None
        phase = value.get("failure_stage")
        if not isinstance(phase, str) or phase not in _FAILURE_PHASES:
            return None
        usage = value.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        return cls(
            phase=phase,
            finish_reason=value.get("finish_reason"),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            content_empty=value.get("content_empty"),
        )
