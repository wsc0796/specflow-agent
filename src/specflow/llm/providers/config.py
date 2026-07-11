"""Configuration for an OpenAI-compatible LLM Provider."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from specflow.llm.exceptions import LLMConfigurationError


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    """Validated provider configuration with credential-safe representation."""

    base_url: str
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise LLMConfigurationError("LLM base URL must not be empty")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise LLMConfigurationError("LLM API key must not be empty")
        if not isinstance(self.model, str) or not self.model.strip():
            raise LLMConfigurationError("LLM model must not be empty")
        if (
            not isinstance(self.timeout_seconds, int | float)
            or isinstance(self.timeout_seconds, bool)
            or not math.isfinite(float(self.timeout_seconds))
            or not 0 < float(self.timeout_seconds) <= 600
        ):
            raise LLMConfigurationError("LLM timeout must be between 0 and 600 seconds")

        base_url = self.base_url.strip().rstrip("/")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise LLMConfigurationError("LLM base URL must be an HTTP(S) URL with a host")
        if parsed.username is not None or parsed.password is not None:
            raise LLMConfigurationError("LLM base URL must not contain credentials")
        if parsed.query or parsed.fragment:
            raise LLMConfigurationError("LLM base URL must not contain query or fragment")

        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "api_key", self.api_key.strip())
        object.__setattr__(self, "model", self.model.strip())
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> OpenAICompatibleConfig:
        """Build configuration from explicit environment values or `os.environ`."""
        source = os.environ if environment is None else environment
        timeout_raw = source.get("SPECFLOW_LLM_TIMEOUT_SECONDS", "60")
        timeout: float | None = None
        try:
            timeout = float(timeout_raw)
        except (TypeError, ValueError):
            pass
        if timeout is None:
            raise LLMConfigurationError("LLM timeout must be numeric")
        return cls(
            base_url=source.get("SPECFLOW_LLM_BASE_URL", ""),
            api_key=source.get("SPECFLOW_LLM_API_KEY", ""),
            model=source.get("SPECFLOW_LLM_MODEL", ""),
            timeout_seconds=timeout,
        )

    @property
    def completions_url(self) -> str:
        """Return the one supported OpenAI-compatible endpoint."""
        return f"{self.base_url}/chat/completions"
