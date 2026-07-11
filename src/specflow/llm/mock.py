"""Deterministic mock LLM client."""

from __future__ import annotations

from time import perf_counter

from specflow.llm.exceptions import LLMResponseError
from specflow.llm.models import LLMRequest, LLMResponse, LLMUsage


class MockLLMClient:
    """A deterministic test double for LLMClient."""

    def __init__(
        self,
        response_content: str = "mock response",
        fail_with: Exception | None = None,
    ) -> None:
        self._response_content = response_content
        self._fail_with = fail_with

    def complete(self, request: LLMRequest) -> LLMResponse:
        start = perf_counter()
        try:
            if self._fail_with is not None:
                raise self._fail_with
            input_tokens = sum(
                max(1, (len(message.content) + 3) // 4) for message in request.messages
            )
            output_tokens = max(1, (len(self._response_content) + 3) // 4)
            return LLMResponse(
                content=self._response_content,
                model=request.model,
                usage=LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens),
                latency_ms=max(0, int((perf_counter() - start) * 1000)),
                finish_reason="stop",
            )
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMResponseError(f"Mock LLM failed: {type(exc).__name__}") from exc
