"""Optional hardening for the HTTP entry point.

The service is designed for a single-user, localhost-only deployment.  The
controls below are opt-in through environment variables so the default
portfolio workflow remains unchanged:

- ``SPECFLOW_API_KEY``: when set, every ``/api/v1`` request must present the
  key via ``X-API-Key`` or ``Authorization: Bearer``.
- ``SPECFLOW_ALLOWED_REPOSITORY_ROOTS``: when set (``;``-separated paths),
  registered ``repository_path`` values must resolve inside one of them.
- ``SPECFLOW_REVIEWER_LABELS``: when set (comma-separated), review decisions
  must use one of these labels.
- ``SPECFLOW_MAX_RUNS_PER_MINUTE`` and ``SPECFLOW_MAX_CONCURRENT_RUNS``:
  quotas for the run-creation endpoint.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import deque
from collections.abc import Mapping
from pathlib import Path

from fastapi import Header, HTTPException, Request, status


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        return None
    return token.strip()


def _positive_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


class RunRateLimiter:
    """In-process quotas for the run-creation endpoint.

    Enforces a sliding per-minute window and a maximum number of concurrent
    runs.  This is a single-process guard: multi-process deployments need a
    shared limiter (e.g. Redis) instead.
    """

    def __init__(self, per_minute: int = 30, max_concurrent: int = 1) -> None:
        self._per_minute = per_minute
        self._max_concurrent = max_concurrent
        self._semaphore = threading.BoundedSemaphore(max_concurrent)
        self._window: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> RunPermit:
        if not self._semaphore.acquire(blocking=False):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Another run is already in progress.",
            )

        now = time.monotonic()
        with self._lock:
            while self._window and now - self._window[0] > 60.0:
                self._window.popleft()
            if len(self._window) >= self._per_minute:
                self._semaphore.release()
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Run rate limit exceeded. Try again later.",
                )
            self._window.append(now)
        return RunPermit(self)


class RunPermit:
    """Releases the concurrency slot when a run finishes."""

    def __init__(self, limiter: RunRateLimiter) -> None:
        self._limiter = limiter

    def release(self) -> None:
        self._limiter._semaphore.release()


class ApiSecurity:
    """Opt-in authentication, path allowlisting, and run quotas."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        allowed_repository_roots: tuple[str, ...] = (),
        reviewer_labels: frozenset[str] = frozenset(),
        max_runs_per_minute: int = 30,
        max_concurrent_runs: int = 1,
    ) -> None:
        self.api_key = api_key
        self._allowed_roots = tuple(
            Path(root).expanduser().resolve() for root in allowed_repository_roots
        )
        self.reviewer_labels = reviewer_labels
        self._rate_limiter = RunRateLimiter(max_runs_per_minute, max_concurrent_runs)

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> ApiSecurity:
        source = os.environ if environment is None else environment
        api_key = source.get("SPECFLOW_API_KEY") or None
        roots_raw = source.get("SPECFLOW_ALLOWED_REPOSITORY_ROOTS", "")
        roots = tuple(
            root.strip() for root in roots_raw.replace("|", ";").split(";") if root.strip()
        )
        labels_raw = source.get("SPECFLOW_REVIEWER_LABELS", "")
        labels = frozenset(label.strip() for label in labels_raw.split(",") if label.strip())
        return cls(
            api_key=api_key,
            allowed_repository_roots=roots,
            reviewer_labels=labels,
            max_runs_per_minute=_positive_int(source.get("SPECFLOW_MAX_RUNS_PER_MINUTE", "30"), 30),
            max_concurrent_runs=_positive_int(source.get("SPECFLOW_MAX_CONCURRENT_RUNS", "1"), 1),
        )

    # ── dependency hooks ─────────────────────────────────────────

    def require_api_key(
        self,
        request: Request,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> None:
        """Reject unauthenticated API calls when a key is configured."""
        if not self.api_key:
            return
        provided = x_api_key or _bearer_token(authorization)
        if not provided or not secrets.compare_digest(provided, self.api_key):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or missing API key.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def validate_repository_path(self, repository_path: str) -> Path:
        """Return the resolved path, or reject it outside the allowlist."""
        candidate = Path(repository_path).expanduser().resolve()
        if not self._allowed_roots:
            return candidate
        if not any(self._is_within(candidate, root) for root in self._allowed_roots):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "repository_path is not inside an allowed repository root.",
            )
        return candidate

    def validate_reviewer_label(self, reviewer_label: str) -> None:
        """Reject unapproved reviewer labels when an allowlist is configured."""
        if self.reviewer_labels and reviewer_label not in self.reviewer_labels:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "reviewer_label is not in the approved list.",
            )

    def rate_limit_create_run(self) -> RunPermit:
        """Acquire a run slot; raises HTTP 429 when quotas are exhausted."""
        return self._rate_limiter.acquire()

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False
