"""One shared admission and accounting boundary for a run's LLM requests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Lock

from specflow.llm.client import LLMClient
from specflow.llm.models import LLMRequest, LLMResponse, LLMUsage
from specflow.policy import ExecutionPolicy, RuntimeGuard, SpecFlowError


class LLMCallBudget:
    """Reserve output capacity before sending; record usage before parsing.

    Input usage cannot be known before a response. Reservations bound requested
    output capacity, not actual provider billing or already-started requests.
    """

    def __init__(self, guard: RuntimeGuard, policy: ExecutionPolicy) -> None:
        self._guard = guard
        self._policy = policy
        self._lock = Lock()
        self._reserved_output = 0
        self._pending_requests = 0
        self._observed_input = 0
        self._observed_output = 0
        self._observed_calls = 0
        self._failure: tuple[str, str] | None = None

    def wrap(
        self,
        client: LLMClient,
        *,
        on_request: Callable[[LLMRequest], None] | None = None,
    ) -> LLMClient:
        return _BudgetedLLMClient(self, client, on_request)

    def _stop(self, error: SpecFlowError) -> None:
        if self._failure is None:
            self._failure = (error.code, error.safe_message)

    def _check_open(self) -> None:
        if self._failure is not None:
            raise SpecFlowError(code=self._failure[0], safe_message=self._failure[1])
        if self._guard.remaining_time() <= 0:
            raise SpecFlowError(code="TIME_BUDGET_EXCEEDED", safe_message="Run deadline exceeded")

    def check(self) -> None:
        """Stop after a final enrichment failure even if its fallback caught it."""
        with self._lock:
            self._check_open()

    def complete(
        self,
        client: LLMClient,
        request: LLMRequest,
        on_request: Callable[[LLMRequest], None] | None = None,
    ) -> LLMResponse:
        with self._lock:
            try:
                self._check_open()
                if self._guard.llm_calls + self._pending_requests >= self._policy.max_llm_calls:
                    raise SpecFlowError(
                        code="CALL_BUDGET_EXCEEDED", safe_message="LLM call budget exceeded"
                    )
                tokens = self._policy.tokens
                available = (
                    min(
                        tokens.max_run_output_tokens - self._observed_output,
                        tokens.max_run_total_tokens
                        - tokens.reserved_retry_tokens
                        - self._observed_input
                        - self._observed_output,
                    )
                    - self._reserved_output
                )
                if self._observed_input >= tokens.max_run_input_tokens or available <= 0:
                    raise SpecFlowError(
                        code="TOKEN_BUDGET_EXCEEDED", safe_message="No remaining token budget"
                    )
                reserved = min(request.max_tokens, tokens.max_agent_output_tokens, available)
                timeout = self._guard.remaining_time()
                if timeout <= 0:
                    raise SpecFlowError(
                        code="TIME_BUDGET_EXCEEDED", safe_message="Run deadline exceeded"
                    )
                if request.timeout_seconds is not None:
                    timeout = min(timeout, request.timeout_seconds)
                effective = replace(request, max_tokens=reserved, timeout_seconds=timeout)
                self._pending_requests += 1
                self._reserved_output += reserved
            except SpecFlowError as error:
                self._stop(error)
                raise

        # Observation may synchronously wait or write files. Recheck immediately
        # afterwards, counting only requests that reach the provider boundary.
        try:
            if on_request is not None:
                on_request(effective)
            with self._lock:
                self._check_open()
                remaining = self._guard.remaining_time()
                if remaining <= 0:
                    raise SpecFlowError(
                        code="TIME_BUDGET_EXCEEDED", safe_message="Run deadline exceeded"
                    )
                effective = replace(
                    effective, timeout_seconds=min(effective.timeout_seconds, remaining)
                )
                self._guard.consume_llm_call()
                self._pending_requests -= 1
        except Exception as error:
            with self._lock:
                self._pending_requests -= 1
                self._reserved_output -= reserved
                if isinstance(error, SpecFlowError):
                    self._stop(error)
            raise

        try:
            response = client.complete(effective)
        except Exception as error:
            with self._lock:
                self._reserved_output -= reserved
                self._stop(
                    error
                    if isinstance(error, SpecFlowError)
                    else SpecFlowError(
                        code="TOKEN_USAGE_UNAVAILABLE",
                        safe_message="LLM token usage unavailable after a failed request",
                    )
                )
            # Preserve the provider's classification for the current failure.
            # Any later admission is blocked because its cost is unknown.
            raise

        with self._lock:
            self._reserved_output -= reserved
            try:
                usage = getattr(response, "usage", None)
                if not isinstance(usage, LLMUsage) or any(
                    type(value) is not int or value < 0
                    for value in (usage.input_tokens, usage.output_tokens)
                ):
                    raise SpecFlowError(
                        code="TOKEN_USAGE_UNAVAILABLE", safe_message="LLM token usage unavailable"
                    )
                # Keep observed overages even when RuntimeGuard rejects them.
                self._observed_input += usage.input_tokens
                self._observed_output += usage.output_tokens
                self._observed_calls += 1
                self._guard.consume_tokens(usage.input_tokens, usage.output_tokens)
                self._check_open()
            except SpecFlowError as error:
                self._stop(error)
                raise
        return response

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            calls = self._guard.llm_calls
            return {
                "llm_calls": calls,
                "observed_input_tokens": self._observed_input,
                "observed_output_tokens": self._observed_output,
                "usage_observed_calls": self._observed_calls,
                "usage_unknown_calls": calls - self._observed_calls,
                "usage_complete": calls == self._observed_calls,
                "scope": "all_llm_requests",
            }


@dataclass(frozen=True)
class _BudgetedLLMClient:
    budget: LLMCallBudget
    delegate: LLMClient
    on_request: Callable[[LLMRequest], None] | None = None

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self.budget.complete(self.delegate, request, self.on_request)
