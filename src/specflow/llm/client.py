"""Provider-neutral LLM client protocol."""

from __future__ import annotations

from typing import Protocol

from specflow.llm.models import LLMRequest, LLMResponse


class LLMClient(Protocol):
    """Protocol implemented by mock and future provider-specific clients."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return one completion response for *request*."""
