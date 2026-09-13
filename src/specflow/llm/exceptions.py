"""LLM client exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specflow.policy.errors import ErrorCode


class LLMError(Exception):
    """Base error for provider-neutral LLM client failures."""

    def __init__(self, message: str, *, code: ErrorCode | None = None) -> None:
        super().__init__(message)
        self.code = code


class LLMCircuitError(LLMError):
    """Safe non-retryable rejection, with no internal resource identity."""

    def __init__(self, reason: str) -> None:
        from specflow.policy.errors import ErrorCode

        if reason not in {"open", "probe_limit", "registry_capacity"}:
            raise ValueError("Invalid circuit rejection reason")
        super().__init__(
            "Provider circuit rejected the attempt.", code=ErrorCode.PROVIDER_CIRCUIT_REJECTED
        )
        self.reason = reason


class LLMConfigurationError(LLMError):
    """Raised when a provider cannot be built from safe, complete configuration."""


class LLMTimeoutError(LLMError):
    """Raised when a provider request times out."""


class LLMResponseError(LLMError):
    """Raised when a provider response is invalid or unavailable."""
