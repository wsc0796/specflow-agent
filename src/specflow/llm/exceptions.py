"""LLM client exceptions."""


class LLMError(Exception):
    """Base error for provider-neutral LLM client failures."""


class LLMTimeoutError(LLMError):
    """Raised when a provider request times out."""


class LLMResponseError(LLMError):
    """Raised when a provider response is invalid or unavailable."""
