"""Provider-neutral LLM request and response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from specflow.llm.exceptions import LLMResponseError

LLMRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    """A single chat-style LLM message."""

    role: LLMRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise LLMResponseError(f"Unsupported message role: {self.role}")
        if not self.content.strip():
            raise LLMResponseError("Message content must not be empty")


@dataclass(frozen=True)
class LLMRequest:
    """Provider-neutral request for one completion call."""

    model: str
    messages: list[LLMMessage]
    temperature: float = 0.0
    max_tokens: int = 1024
    response_format: str | None = None

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise LLMResponseError("LLMRequest.model must not be empty")
        if not self.messages:
            raise LLMResponseError("LLMRequest.messages must not be empty")
        if not 0 <= self.temperature <= 2:
            raise LLMResponseError("LLMRequest.temperature must be between 0 and 2")
        if self.max_tokens <= 0:
            raise LLMResponseError("LLMRequest.max_tokens must be positive")


@dataclass(frozen=True)
class LLMUsage:
    """Token usage returned by an LLM provider."""

    input_tokens: int
    output_tokens: int
    total_tokens: int = field(init=False)

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise LLMResponseError("LLMUsage token counts must not be negative")
        object.__setattr__(self, "total_tokens", self.input_tokens + self.output_tokens)


@dataclass(frozen=True)
class LLMResponse:
    """Provider-neutral LLM response."""

    content: str
    model: str
    usage: LLMUsage
    latency_ms: int
    finish_reason: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise LLMResponseError("LLMResponse.content must not be empty")
        if not self.model.strip():
            raise LLMResponseError("LLMResponse.model must not be empty")
        if self.latency_ms < 0:
            raise LLMResponseError("LLMResponse.latency_ms must not be negative")
        if not self.finish_reason.strip():
            raise LLMResponseError("LLMResponse.finish_reason must not be empty")
