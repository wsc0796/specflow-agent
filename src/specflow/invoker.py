"""GuardedModelInvoker — the single controlled entry point for provider calls.

Every real provider request in the multi-agent runtime goes through
:meth:`GuardedModelInvoker.invoke`.  The invoker owns the retry loop, so every
attempt is reserved, settled, and trace-recorded exactly once by the
run-scoped :class:`~specflow.policy.runtime_guard.RuntimeGuard`.  Mock
execution bypasses provider accounting and is recorded as synthetic instead.
"""

from __future__ import annotations

import time

from specflow.llm.client import LLMClient
from specflow.llm.models import LLMRequest, LLMResponse
from specflow.policy.errors import ErrorCode, is_retryable
from specflow.policy.runtime_guard import RuntimeGuard


def classify_provider_error(error: Exception) -> ErrorCode:
    """Classify a provider failure into the shared retry taxonomy."""
    if isinstance(error, TimeoutError):
        return ErrorCode.PROVIDER_TIMEOUT
    text = str(error).lower()
    if "401" in text or "auth" in text or "unauthorized" in text:
        return ErrorCode.PROVIDER_AUTH_FAILURE
    if "429" in text or "rate" in text:
        return ErrorCode.PROVIDER_RATE_LIMITED
    if "timeout" in text or "timed out" in text:
        return ErrorCode.PROVIDER_TIMEOUT
    if "connection" in text or "network" in text:
        return ErrorCode.PROVIDER_CONNECTION_ERROR
    if any(code in text for code in ("500", "502", "503", "server")):
        return ErrorCode.PROVIDER_SERVER_ERROR
    return ErrorCode.INTERNAL_UNEXPECTED


class GuardedModelInvoker:
    """Route provider calls through one guarded, retrying, accounting entry."""

    def __init__(
        self,
        client: LLMClient,
        guard: RuntimeGuard,
        *,
        max_provider_retries: int = 0,
        base_backoff_seconds: float = 0.5,
    ) -> None:
        self._client = client
        self._guard = guard
        self._max_provider_retries = max(0, max_provider_retries)
        self._base_backoff = max(0.0, base_backoff_seconds)

    def invoke(
        self,
        request: LLMRequest,
        *,
        call_type: str,
        agent_id: str | None = None,
        revision_id: str | None = None,
    ) -> LLMResponse:
        """Execute one logical model call with per-attempt budget accounting.

        Returns the successful response, or raises the last provider error
        after retries are exhausted.  Budget rejections are never retried and
        propagate as :class:`SpecFlowError` before any request is sent.
        """
        if self._guard.execution_mode == "mock":
            response = self._client.complete(request)
            self._guard.record_synthetic_model_call(call_type=call_type)
            return response

        attempt = 0
        while True:
            attempt += 1
            reservation = self._guard.reserve_provider_attempt(
                call_type=call_type,
                agent_id=agent_id,
                revision_id=revision_id,
            )
            started = time.perf_counter()
            try:
                response = self._client.complete(request)
            except Exception as error:
                latency_ms = max(0, int((time.perf_counter() - started) * 1000))
                error_code = classify_provider_error(error)
                self._guard.release_provider_attempt(
                    reservation,
                    success=False,
                    error_code=error_code.value,
                    latency_ms=latency_ms,
                )
                retryable = is_retryable(error_code)
                if not retryable or attempt > self._max_provider_retries:
                    raise
                self._guard.record_model_call_event(
                    {
                        "event_type": "MODEL_CALL_RETRYING",
                        "call_type": reservation.call_type,
                        "agent_id": reservation.agent_id,
                        "revision_id": reservation.revision_id,
                        "attempt_index": attempt,
                    }
                )
                if self._base_backoff:
                    time.sleep(min(self._base_backoff * (2 ** (attempt - 1)), 5.0))
                continue

            latency_ms = max(0, int((time.perf_counter() - started) * 1000))
            usage = getattr(response, "usage", None)
            self._guard.release_provider_attempt(
                reservation,
                success=True,
                latency_ms=latency_ms,
                input_tokens=usage.input_tokens if usage is not None else None,
                output_tokens=usage.output_tokens if usage is not None else None,
            )
            return response
