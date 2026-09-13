"""Bounded, process-local circuit state for actual provider attempts only."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256

import httpx

from specflow.llm.exceptions import LLMCircuitError, LLMError
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.policy.errors import ErrorCode

_AVAILABILITY_FAILURES = frozenset(
    {
        ErrorCode.PROVIDER_TIMEOUT,
        ErrorCode.PROVIDER_RATE_LIMITED,
        ErrorCode.PROVIDER_SERVER_ERROR,
        ErrorCode.PROVIDER_CONNECTION_ERROR,
    }
)


@dataclass(frozen=True)
class ResilienceSettings:
    failure_threshold: int = 5
    open_seconds: float = 30.0
    half_open_max_probes: int = 1
    max_entries: int = 128

    def __post_init__(self) -> None:
        for value in (self.failure_threshold, self.half_open_max_probes, self.max_entries):
            if type(value) is not int or value <= 0:
                raise ValueError("Circuit bounds must be positive integers")
        if (
            isinstance(self.open_seconds, bool)
            or not isinstance(self.open_seconds, int | float)
            or not math.isfinite(self.open_seconds)
            or self.open_seconds <= 0
        ):
            raise ValueError("Circuit open duration must be positive and finite")


@dataclass(frozen=True)
class ResourceIdentity:
    """Internal, non-persisted digests; never an audit representation."""

    backend_resource_identity: str = field(repr=False)
    effective_model: str = field(repr=False)
    provider_tenancy_discriminator: str = field(repr=False)

    def __post_init__(self) -> None:
        for value in (
            self.backend_resource_identity,
            self.effective_model,
            self.provider_tenancy_discriminator,
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError("Circuit identity requires fixed-length digests")


def resource_identity(config: OpenAICompatibleConfig) -> ResourceIdentity:
    """Bind the effective HTTP endpoint, wire model, and credential tenancy."""
    return ResourceIdentity(
        sha256(str(httpx.URL(config.completions_url)).encode()).hexdigest(),
        sha256(config.model.encode()).hexdigest(),
        sha256(config.api_key.encode()).hexdigest(),
    )


@dataclass(frozen=True)
class CircuitSnapshot:
    """Safe observations for future metrics; aliases name resident slots only."""

    provider_resource_alias: str
    model_alias: str
    state: str
    failure_count: int
    consecutive_failures: int
    active_calls: int
    active_probes: int
    rejection_count: int
    transition_count: int


@dataclass
class _Entry:
    alias: int
    state: str = "CLOSED"
    generation: int = 0
    opened_at: float = 0.0
    failure_count: int = 0
    consecutive_failures: int = 0
    active_calls: int = 0
    active_probes: int = 0
    rejection_count: int = 0
    transition_count: int = 0


class ProviderResilienceGuard:
    """Own circuit state, never retries, transport, fallback, or a recovery task."""

    def __init__(
        self,
        settings: ResilienceSettings = ResilienceSettings(),
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[ResourceIdentity, _Entry] = {}

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @contextmanager
    def attempt(self, key: ResourceIdentity) -> Iterator[None]:
        entry, generation, probe = self._before_attempt(key)
        success = False
        code = None
        try:
            yield
            success = True
        except LLMError as error:
            code = error.code
            raise
        finally:
            # Includes BaseException and errors with no availability classification.
            self._finish(entry, generation, probe, success, code)

    def _before_attempt(self, key: ResourceIdentity) -> tuple[_Entry, int, bool]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                if len(self._entries) >= self._settings.max_entries:
                    recyclable = next(
                        (
                            candidate
                            for candidate, value in self._entries.items()
                            if value.state == "CLOSED"
                            and value.active_calls == 0
                            and value.consecutive_failures == 0
                        ),
                        None,
                    )
                    if recyclable is None:
                        raise LLMCircuitError("registry_capacity")
                    del self._entries[recyclable]
                used = {value.alias for value in self._entries.values()}
                alias = next(i for i in range(1, self._settings.max_entries + 1) if i not in used)
                entry = self._entries[key] = _Entry(alias)
            if entry.state == "OPEN":
                if self._clock() - entry.opened_at < self._settings.open_seconds:
                    entry.rejection_count += 1
                    raise LLMCircuitError("open")
                self._transition(entry, "HALF_OPEN")
            probe = entry.state == "HALF_OPEN"
            if probe and entry.active_probes >= self._settings.half_open_max_probes:
                entry.rejection_count += 1
                raise LLMCircuitError("probe_limit")
            entry.active_calls += 1
            if probe:
                entry.active_probes += 1
            return entry, entry.generation, probe

    def _finish(
        self, entry: _Entry, generation: int, probe: bool, success: bool, code: ErrorCode | None
    ) -> None:
        with self._lock:
            entry.active_calls -= 1
            if probe:
                entry.active_probes -= 1
            counted = code in _AVAILABILITY_FAILURES
            if counted:
                entry.failure_count += 1
            # Old in-flight results release their slots and count actual failures,
            # but cannot overwrite a newer OPEN/HALF_OPEN generation.
            if generation != entry.generation:
                return
            if counted:
                entry.consecutive_failures = min(
                    entry.consecutive_failures + 1, self._settings.failure_threshold
                )
                if probe or entry.consecutive_failures >= self._settings.failure_threshold:
                    entry.opened_at = self._clock()
                    self._transition(entry, "OPEN")
            elif success:
                entry.consecutive_failures = 0
                if probe and entry.active_probes == 0:
                    self._transition(entry, "CLOSED")
            # Excluded failures leave health unchanged; HALF_OPEN stays available
            # for a later bounded probe, with this call's slot already released.

    @staticmethod
    def _transition(entry: _Entry, state: str) -> None:
        entry.state = state
        entry.generation += 1
        entry.transition_count += 1

    def snapshot(self, key: ResourceIdentity) -> CircuitSnapshot | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            return CircuitSnapshot(
                provider_resource_alias=f"resource-{entry.alias}",
                model_alias=f"model-{entry.alias}",
                state=entry.state,
                failure_count=entry.failure_count,
                consecutive_failures=entry.consecutive_failures,
                active_calls=entry.active_calls,
                active_probes=entry.active_probes,
                rejection_count=entry.rejection_count,
                transition_count=entry.transition_count,
            )


DEFAULT_RESILIENCE_GUARD = ProviderResilienceGuard()
