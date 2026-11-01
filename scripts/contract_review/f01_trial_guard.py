"""Trial-only DeepSeek Flash accounting; no CLI sessions or credential discovery.

The official full context ceiling is deliberately used as the input billing
bound. Character ratios and the downloadable tokenizer's estimates are not
substitutes for a demonstrated bound. The approved CNY 2 trial is restricted
to its verified off-peak execution window; every request rechecks that window.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import httpx

from specflow.contract_review.common import digest
from specflow.contract_review.provider import OpenAIReviewAdapter, ProviderFailure
from specflow.contract_review.sources import strict_json

REQUEST_MODEL = "deepseek-v4-flash"
RESPONSE_MODELS = frozenset((REQUEST_MODEL, "deepseek-flash"))
PROVIDER_BASE = "https://api.deepseek.com"
LAUNCHER_BASE = PROVIDER_BASE + "/anthropic"
PRICING_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
MODEL_URL = "https://api-docs.deepseek.com/api/list-models/"
ALIAS_URL = "https://api-docs.deepseek.com/quick_start/agent_integrations/"
VERIFIED_ON = "2026-11-01"
MICROYUAN = Decimal("0.000001")
WINDOW_START = datetime(2026, 11, 1, 10, tzinfo=UTC)
WINDOW_END = datetime(2026, 11, 1, 16, tzinfo=UTC)


def timestamp():
    return datetime.now(UTC).isoformat()


def rounded(value):
    return value.quantize(MICROYUAN, rounding=ROUND_CEILING)


class TrialStopped(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def utc_now():
    return datetime.now(UTC)


def require_execution_window(observed=None):
    instant = utc_now() if observed is None else observed
    if instant.tzinfo is None or not WINDOW_START <= instant < WINDOW_END:
        raise TrialStopped("TRIAL_OFF_PEAK_WINDOW_REQUIRED")


@dataclass(frozen=True)
class FlashPolicy:
    budget_cny: Decimal = Decimal("2")
    call_limit: int = 12
    input_token_bound: int = 1_048_576
    input_cny_per_million: Decimal = Decimal("1")
    output_cny_per_million: Decimal = Decimal("4")
    output_token_limit: int = 8000
    evidence: str = "official-context-ceiling-2026-11-01"

    def __post_init__(self):
        if (
            not self.budget_cny.is_finite()
            or not Decimal("0") < self.budget_cny <= Decimal("2")
            or type(self.call_limit) is not int
            or not 1 <= self.call_limit <= 12
            or type(self.input_token_bound) is not int
            or self.input_token_bound < 1
            or type(self.output_token_limit) is not int
            or not 1 <= self.output_token_limit <= 8000
            or any(
                not rate.is_finite() or rate <= 0
                for rate in (self.input_cny_per_million, self.output_cny_per_million)
            )
        ):
            raise ValueError("Invalid bounded trial policy")

    def quote(self, output_tokens=None):
        output = self.output_token_limit if output_tokens is None else output_tokens
        if type(output) is not int or not 1 <= output <= self.output_token_limit:
            raise ValueError("Invalid output ceiling")
        return rounded(
            (
                self.input_token_bound * self.input_cny_per_million
                + output * self.output_cny_per_million
            )
            / Decimal(1_000_000)
        )

    def record(self):
        return {
            "currency": "CNY",
            "budget_cny": str(self.budget_cny),
            "model_call_limit": self.call_limit,
            "input_token_bound": self.input_token_bound,
            "max_output_tokens": self.output_token_limit,
            "input_cny_per_million_upper": str(self.input_cny_per_million),
            "output_cny_per_million_upper": str(self.output_cny_per_million),
            "reservation_cny": str(self.quote()),
            "input_bound_evidence": self.evidence,
            "verified_on": VERIFIED_ON,
            "pricing_source": PRICING_URL,
            "context_source": MODEL_URL,
            "alias_source": ALIAS_URL,
            "requested_model": REQUEST_MODEL,
            "provider_serving_version_reported_by_docs": "DeepSeek-V4.1-Flash-1017",
            "billing_basis": "off-peak, cache-miss upper rate; not a provider invoice",
            "not_before_utc": WINDOW_START.isoformat(),
            "expires_utc": WINDOW_END.isoformat(),
            "execution_window_shanghai": "2026-11-01 18:00 through 24:00 (exclusive)",
            "thinking_policy": "provider documented default enabled/high",
            "temperature_effective": False,
            "server_tools": "not requested",
        }

    def require_first_dispatch(self):
        require_execution_window()
        if self.quote() > self.budget_cny:
            raise TrialStopped("BUDGET_PRECHECK_FAILED")


class TrialLedger:
    """Bounded single-process journal; reservations survive every unknown result."""

    def __init__(self, policy: FlashPolicy, path: Path):
        self.policy = policy
        self._lock = threading.RLock()
        self._stream = path.open("x", encoding="utf-8", newline="\n")
        self._calls = {}
        self._cost = Decimal("0")
        self._reserved = Decimal("0")
        self._http_attempts = set()
        self._response_models = {}
        self._halt = None
        self._journal_bytes = 0

    def _write(self, event, **body):
        record = {"event": event, "at": timestamp(), "monotonic": time.monotonic(), **body}
        raw = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        size = len(raw.encode("utf-8"))
        if self._journal_bytes + size > 8 * 1024**2:
            self._halt = "TRIAL_JOURNAL_CAPACITY"
            raise TrialStopped(self._halt)
        try:
            self._stream.write(raw)
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except OSError:
            self._halt = "TRIAL_JOURNAL_UNAVAILABLE"
            raise TrialStopped(self._halt) from None
        self._journal_bytes += size

    def reserve(self, wire):
        with self._lock:
            if self._halt:
                raise TrialStopped(self._halt)
            if len(self._calls) >= self.policy.call_limit:
                raise TrialStopped("TRIAL_CALL_LIMIT")
            quote = self.policy.quote(wire["max_tokens"])
            if self._cost + self._reserved + quote > self.policy.budget_cny:
                raise TrialStopped("TRIAL_FEE_LIMIT")
            call = uuid.uuid4().hex
            self._write(
                "reserved_before_adapter_http",
                trial_call_id=call,
                wire_hash=digest(wire),
                payload=wire,
                reserved_cny=str(quote),
            )
            self._calls[call] = quote
            self._reserved += quote
            return call

    def http_started(self, call):
        with self._lock:
            require_execution_window()
            if call not in self._calls or call in self._http_attempts or self._halt:
                raise TrialStopped("TRIAL_HTTP_DISPATCH_INVALID")
            self._write("http_transport_entered", trial_call_id=call, remote_receipt="unknown")
            self._http_attempts.add(call)

    def received(self, call, result):
        with self._lock:
            usage = result.get("usage", {})
            self._write("adapter_result", trial_call_id=call, result=result)
            valid_usage = isinstance(usage, dict) and all(
                type(usage.get(name)) is int and usage[name] >= 0
                for name in ("input_tokens", "output_tokens")
            )
            response_model = self._response_models.get(call)
            if not isinstance(response_model, str) or not response_model:
                self._halt = "TRIAL_MODEL_UNKNOWN"
            elif response_model not in RESPONSE_MODELS:
                self._halt = "TRIAL_MODEL_MISMATCH"
            elif not valid_usage:
                self._halt = "TRIAL_USAGE_UNKNOWN"
            elif (
                usage["input_tokens"] > self.policy.input_token_bound
                or usage["output_tokens"] > self.policy.output_token_limit
            ):
                self._halt = "TRIAL_USAGE_BOUND_VIOLATION"
            else:
                charge = rounded(
                    (
                        usage["input_tokens"] * self.policy.input_cny_per_million
                        + usage["output_tokens"] * self.policy.output_cny_per_million
                    )
                    / Decimal(1_000_000)
                )
                if charge > self._calls[call]:
                    self._halt = "TRIAL_USAGE_BOUND_VIOLATION"
                else:
                    self._reserved -= self._calls[call]
                    self._calls[call] = Decimal("0")
                    self._cost += charge
                    self._write(
                        "usage_accounted",
                        trial_call_id=call,
                        usage=usage,
                        cost_cny_upper=str(charge),
                    )
            if self._halt:
                self._write("further_dispatch_stopped", code=self._halt, trial_call_id=call)
            return self._halt

    def observed_response_model(self, call, body, *, complete):
        with self._lock:
            parsed = None
            if complete:
                try:
                    parsed = strict_json(body.decode("utf-8"))
                except (ValueError, UnicodeError):
                    pass
            present = isinstance(parsed, dict) and "model" in parsed
            value = parsed.get("model") if present else None
            valid_type = isinstance(value, str) and 0 < len(value) <= 256
            self._response_models[call] = value if valid_type else None
            self._write(
                "http_response_identity",
                trial_call_id=call,
                model_field_present=present,
                response_model=value if valid_type else None,
                model_field_valid=valid_type,
                response_body_complete=complete,
            )

    def failed(self, call, code, remote_outcome):
        with self._lock:
            self._halt = "TRIAL_PROVIDER_FAILURE"
            self._write(
                "provider_failed",
                trial_call_id=call,
                code=code,
                remote_outcome=remote_outcome,
                reservation_retained=True,
            )

    def summary(self):
        with self._lock:
            return {
                "model_call_reservations": len(self._calls),
                "business_model_http_attempts": len(self._http_attempts),
                "cost_cny_upper_accounted": str(self._cost),
                "unsettled_cny_reserved": str(self._reserved),
                "budget_cny": str(self.policy.budget_cny),
                "billing_status": "unknown" if self._reserved else "usage_accounted_upper",
                "provider_invoice_cost": None,
                "halt_reason": self._halt,
            }

    def close(self):
        with self._lock:
            if not self._stream.closed:
                try:
                    self._write("ledger_closed", summary=self.summary())
                finally:
                    self._stream.close()


class _IdentityStream(httpx.SyncByteStream):
    def __init__(self, delegate, ledger, call):
        self.delegate, self.ledger, self.call = delegate, ledger, call
        self.body = bytearray()
        self.complete, self.closed, self.too_large = False, False, False

    def __iter__(self):
        for chunk in self.delegate:
            if not self.too_large and len(self.body) + len(chunk) <= 128 * 1024:
                self.body.extend(chunk)
            else:
                self.too_large = True
            yield chunk
        self.complete = not self.too_large

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.delegate.close()
            finally:
                self.ledger.observed_response_model(
                    self.call, bytes(self.body), complete=self.complete
                )


class _TrialTransport(httpx.BaseTransport):
    def __init__(self, delegate, ledger, call, wire):
        self.delegate, self.ledger, self.call = delegate, ledger, call
        self.wire_hash = digest(wire)

    def handle_request(self, request):
        if (
            request.method != "POST"
            or request.url.path != "/chat/completions"
            or digest(json.loads(request.content)) != self.wire_hash
        ):
            raise TrialStopped("TRIAL_WIRE_MISMATCH")
        self.ledger.http_started(self.call)
        response = self.delegate.handle_request(request)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_IdentityStream(response.stream, self.ledger, self.call),
            extensions=response.extensions,
        )

    def close(self):
        self.delegate.close()


class GuardedFlashAdapter(OpenAIReviewAdapter):
    """Keep the existing adapter/worker contract, without another execution loop."""

    def __init__(self, config, ledger, *, transport=None, execution_mode="live"):
        if config.model != REQUEST_MODEL:
            raise ValueError("Only the authorized launcher model is accepted")
        if execution_mode == "live" and (
            config.base_url != PROVIDER_BASE or ledger.policy != FlashPolicy()
        ):
            raise ValueError("Live execution requires the frozen official Flash policy")
        super().__init__(config, transport=transport, execution_mode=execution_mode)
        self.trial_ledger = ledger
        self._trial_transport = transport
        self._complete_lock = threading.Lock()

    def complete(self, payload, *, profile):
        if not self._complete_lock.acquire(blocking=False):
            raise ProviderFailure("TRIAL_IO_BUSY", remote_outcome="not_applicable")
        try:
            return self._complete_one(payload, profile)
        finally:
            self._complete_lock.release()

    def _complete_one(self, payload, profile):
        try:
            require_execution_window()
            wire = self.prepare(payload, profile)
            call = self.trial_ledger.reserve(wire)
        except TrialStopped as error:
            raise ProviderFailure(
                error.code,
                usage={"input_tokens": 0, "output_tokens": 0},
                remote_outcome="not_applicable",
            ) from None
        try:
            delegate = self._trial_transport or httpx.HTTPTransport(retries=0, trust_env=False)
            self._transport = _TrialTransport(delegate, self.trial_ledger, call, wire)
            result = super().complete(wire, profile=profile)
        except ProviderFailure as error:
            self.trial_ledger.failed(call, error.code, error.remote_outcome)
            raise ProviderFailure(
                error.code,
                retryable=False,
                usage=error.usage,
                remote_outcome=error.remote_outcome,
            ) from None
        except Exception:
            self.trial_ledger.failed(call, "PROVIDER_ERROR", "unknown")
            raise ProviderFailure("PROVIDER_ERROR") from None
        stopped = self.trial_ledger.received(call, result)
        if stopped in (
            "TRIAL_MODEL_UNKNOWN",
            "TRIAL_MODEL_MISMATCH",
            "TRIAL_USAGE_BOUND_VIOLATION",
        ):
            raise ProviderFailure(stopped, usage=result.get("usage"), remote_outcome="known")
        return result
