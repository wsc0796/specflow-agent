"""Trace recording and LLM client integration."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from specflow.llm import LLMClient, LLMError, LLMRequest, LLMResponse
from specflow.trace.models import LLMTrace
from specflow.trace.storage import JsonTraceStorage


class TraceRecorder:
    """Record metadata-only traces for LLM calls."""

    def __init__(self, storage: JsonTraceStorage) -> None:
        self._storage = storage

    def record(self, trace: LLMTrace):
        """Persist one trace and return the written path."""
        return self._storage.write(trace)

    def complete_with_trace(
        self,
        client: LLMClient,
        request: LLMRequest,
        prompt_name: str,
        prompt_version: str,
        prompt_hash: str,
        context_hash: str,
        run_id: str | None = None,
    ) -> LLMResponse:
        safe_run_id = run_id or uuid4().hex
        start = perf_counter()
        try:
            response = client.complete(request)
            elapsed_ms = max(response.latency_ms, int((perf_counter() - start) * 1000))
            self.record(
                LLMTrace(
                    run_id=safe_run_id,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    prompt_hash=prompt_hash,
                    context_hash=context_hash,
                    model=response.model,
                    latency_ms=elapsed_ms,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    status="success",
                )
            )
            return response
        except LLMError as exc:
            elapsed_ms = max(0, int((perf_counter() - start) * 1000))
            self.record(
                LLMTrace(
                    run_id=safe_run_id,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    prompt_hash=prompt_hash,
                    context_hash=context_hash,
                    model=request.model,
                    latency_ms=elapsed_ms,
                    input_tokens=0,
                    output_tokens=0,
                    status="failed",
                    error_type=type(exc).__name__,
                )
            )
            raise
