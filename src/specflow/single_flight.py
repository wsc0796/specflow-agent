"""Process-local in-flight ownership; completed results are never retained."""

from __future__ import annotations

import fnmatch
import math
import os
import re
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from specflow.llm import OpenAICompatibleConfig
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.policy import DEFAULT_POLICY, ExecutionPolicy, SpecFlowError
from specflow.policy.models import RunOutcome, RunStatus
from specflow.tools.exceptions import BinaryFileError
from specflow.tools.repository_policy import RepositoryAccessPolicy
from specflow.tools.repository_tools import _read_text

# Explicit compatibility versions: bump the affected entry when its behavior
# changes. These describe existing contracts, not a new topology or schema.
CONTRACT_VERSIONS = (
    ("key", "1"),
    ("topology", "fixed-six-v1"),
    ("schema", "strict-v1"),
    ("prompt", "workers-v1"),
    ("enrichment", "1.0.0"),
    ("sanitizer", "t063-v1"),
    ("artifacts", "t069-v1"),
    ("evidence", "bounded-python-v1"),
)
SNAPSHOT_MAX_ENTRIES = 10_000
SNAPSHOT_MAX_BYTES = 8 * 1024 * 1024
_EVIDENCE_PATTERNS = ("*.py", "*.md", "*.yaml", "*.yml", "*.toml", "*.cfg")
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


def safe_code(code: object, fallback: str = "RUNNER_FAILED") -> str:
    return code if isinstance(code, str) and _SAFE_CODE.fullmatch(code) else fallback


def repository_snapshot(repo: Path, policy: ExecutionPolicy = DEFAULT_POLICY) -> str:
    """Hash the bounded evidence read surface through existing path/read rules.

    No Git traversal, full-file hashing, or persistent source-hash change.
    Directory entries and total prefix bytes are bounded in addition to the
    existing 262144-byte per-file read. Repository mutation during execution is
    unsupported; a detected change or incomplete scan fails closed.
    """
    try:
        access = RepositoryAccessPolicy(repo)
        root = repo.resolve(strict=True)
        pending = [root]
        entries = 0
        consumed = 0
        records: list[tuple[str, str, bool]] = []
        while pending:
            directory = pending.pop()
            before_directory = directory.stat()
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries += 1
                    if entries > min(SNAPSHOT_MAX_ENTRIES, policy.repository.max_scanned_files):
                        raise ValueError("snapshot limit")
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    # Reuse the same link/reparse and ignored-directory rules.
                    if access._is_link_or_reparse_point(path):
                        # _repo_summary observes pyproject existence, even a link.
                        if relative == "pyproject.toml":
                            raise ValueError("unsafe summary input")
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if not access._should_skip_directory(path, entry.name):
                            pending.append(path)
                        continue
                    if access.is_sensitive_path(relative):
                        continue
                    if not any(fnmatch.fnmatchcase(relative, p) for p in _EVIDENCE_PATTERNS):
                        continue
                    path, relative = access.resolve_file(relative)
                    before = path.stat()
                    # Match the actual Tool reader, not a larger policy limit.
                    byte_limit = access.limits.max_file_bytes
                    consumed += min(before.st_size, byte_limit + 1)
                    if consumed > SNAPSHOT_MAX_BYTES:
                        raise ValueError("snapshot byte limit")
                    try:
                        content, truncated = _read_text(path, byte_limit)
                        digest = sha256(content.encode("utf-8")).hexdigest()
                    except BinaryFileError:
                        # Both search/read reject this prefix; bytes outside the
                        # Tool read window cannot affect evidence.
                        digest, truncated = "unreadable-text", False
                    after = path.stat()
                    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise ValueError("repository changed")
                    records.append((relative, digest, truncated))
            if directory.stat().st_mtime_ns != before_directory.st_mtime_ns:
                raise ValueError("repository changed")
        return sha256(canonical_json_bytes(sorted(records))).hexdigest()
    except Exception:
        pass
    # Raise outside except so sensitive underlying exceptions are not chained.
    raise SpecFlowError("SINGLE_FLIGHT_SNAPSHOT_UNAVAILABLE", "Safe snapshot unavailable.")


@dataclass(frozen=True)
class PreparedRun:
    key: str = field(repr=False)
    provider_config: OpenAICompatibleConfig | None = field(default=None, repr=False)


def prepare_run(
    *,
    repo: Path,
    requirement: str,
    mode: str,
    mock: bool,
    provider: str,
    model: str,
    policy: ExecutionPolicy = DEFAULT_POLICY,
    versions: tuple[tuple[str, str], ...] = CONTRACT_VERSIONS,
    extra: Mapping[str, Any] | None = None,
) -> PreparedRun:
    snapshot = repository_snapshot(repo, policy)
    config = None
    use_mock = mock or provider == "mock"
    provider_inputs: dict[str, object] = {"provider": "mock", "model": "mock-model"}
    if not use_mock:
        try:
            config = OpenAICompatibleConfig.from_env()
        except Exception:
            pass
        if config is None:
            raise SpecFlowError("PROVIDER_CONFIGURATION_FAILED", "Provider configuration failed.")
        provider_inputs = {
            "provider": provider,
            "model": config.model,
            "endpoint": config.base_url,
            "timeout": min(config.timeout_seconds, policy.max_wall_time_seconds)
            if mode == "multi-agent"
            else config.timeout_seconds,
            # Different credentials can select different provider tenancy.
            # This digest is process memory only; the key is never published.
            "credential": sha256(config.api_key.encode()).hexdigest(),
        }
    key = sha256(
        canonical_json_bytes(
            {
                "repository": str(repo.resolve()),
                "repository_label": repo.name,
                "summary_pyproject_exists": (repo / "pyproject.toml").exists(),
                "snapshot": snapshot,
                "requirement": sha256(requirement.encode()).hexdigest(),
                "mode": mode,
                "mock": use_mock,
                "effective_provider": provider_inputs,
                # Requested labels affect multi-agent provenance and live legacy
                # worker traces/manifests, even when the wire model is env-selected.
                "requested_labels": [provider, model]
                if mode == "multi-agent" or not use_mock
                else [],
                "policy": policy.policy_hash(),
                "versions": versions,
                "extra": dict(extra or {}),
            }
        )
    ).hexdigest()
    return PreparedRun(key, config)


class RunResult(int):
    """Immutable runtime outcome with the existing integer exit-code interface.

    Runners create this only after execution and required writes finish. The
    manifest is an audit artifact, not the source for reconstructing this result.
    """

    def __new__(
        cls,
        code: int,
        *,
        error_code: str | None = None,
        artifact_directory: Path | None = None,
        result_status: str | None = None,
        single_flight: dict[str, str] | None = None,
    ) -> RunResult:
        result = super().__new__(cls, code)
        default_status, default_error = {
            0: (RunStatus.COMPLETED, ""),
            4: (RunStatus.COMPLETED_DEGRADED, ""),
            2: (RunStatus.FAILED_SECURITY, "REPOSITORY_UNAVAILABLE"),
        }.get(code, (RunStatus.FAILED_RUNTIME, "RUNNER_FAILED"))
        outcome = RunOutcome(
            status=result_status or default_status,
            error_code=safe_code(error_code) if error_code else default_error,
            degraded=code == 4,
        )
        object.__setattr__(result, "_outcome", outcome)
        object.__setattr__(result, "_artifact_directory", artifact_directory)
        object.__setattr__(result, "_metadata", tuple((single_flight or {}).items()))
        return result

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("RunResult is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("RunResult is immutable")

    @property
    def error_code(self) -> str | None:
        return self._outcome.error_code or None

    @property
    def result_status(self) -> str:
        return self._outcome.status

    @property
    def artifact_directory(self) -> Path | None:
        return self._artifact_directory

    @property
    def single_flight(self) -> dict[str, str]:
        return dict(self._metadata)

    def with_audit(self, metadata: dict[str, str]) -> RunResult:
        return RunResult(
            int(self),
            error_code=self.error_code,
            artifact_directory=self.artifact_directory,
            result_status=self.result_status,
            single_flight=metadata,
        )


@dataclass
class _Entry:
    owner_run_id: str
    done: threading.Event = field(default_factory=threading.Event)
    outcome: RunResult = field(default_factory=lambda: RunResult(3, error_code="RUNNER_FAILED"))


class Flight:
    def __init__(self, entry: _Entry, owner: bool, prepared: PreparedRun) -> None:
        self._entry = entry
        self.owner = owner
        self.prepared = prepared

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "role": "owner" if self.owner else "follower",
            "owner_run_id": self._entry.owner_run_id,
        }

    def complete(self, result: RunResult) -> RunResult:
        if not self.owner:
            raise SpecFlowError("SINGLE_FLIGHT_OWNERSHIP_ERROR", "Invalid ownership.")
        self._entry.outcome = result.with_audit(self.metadata)
        return self._entry.outcome

    def wait(self, timeout: float) -> RunResult:
        if self.owner or not math.isfinite(timeout) or timeout < 0:
            raise SpecFlowError("SINGLE_FLIGHT_OWNERSHIP_ERROR", "Invalid wait.")
        if not self._entry.done.wait(timeout):
            return RunResult(
                3, error_code="SINGLE_FLIGHT_WAIT_TIMEOUT", single_flight=self.metadata
            )
        return self._entry.outcome.with_audit(self.metadata)


class SingleFlightCoordinator:
    """Only the owning synchronous stack removes an entry after work unwinds."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @contextmanager
    def claim(
        self,
        prepared: PreparedRun,
        owner_run_id: str,
        admit: Callable[[bool], Callable[[], None] | None] | None = None,
    ) -> Iterator[Flight]:
        release = None
        with self._lock:
            entry = self._entries.get(prepared.key)
            owner = entry is None
            # Atomically distinguish followers before quota accounting. An
            # admission rejection cannot create an owner or bypass a quota.
            if admit:
                release = admit(owner)
            if entry is None:
                entry = _Entry(owner_run_id)
                self._entries[prepared.key] = entry
        flight = Flight(entry, owner, prepared)
        try:
            yield flight
        except BaseException as error:
            if owner:
                code = "RUNNER_FAILED" if isinstance(error, Exception) else "RUN_CANCELLED"
                flight.complete(
                    RunResult(
                        3,
                        error_code=code,
                        result_status="cancelled" if code == "RUN_CANCELLED" else None,
                    )
                )
            raise
        finally:
            if owner:
                with self._lock:
                    try:
                        if release:
                            release()
                    finally:
                        del self._entries[prepared.key]
                        entry.done.set()


DEFAULT_COORDINATOR = SingleFlightCoordinator()


def completed_artifact_directory(directory: Path, *, require_complete: bool = False) -> Path | None:
    """Validate a locator after this owner's writer finishes, without parsing it.

    This is not a lookup for previous runs: the caller must have just completed
    the write. The API additionally enforces its own artifact-root boundary.
    """
    try:
        is_link = RepositoryAccessPolicy._is_link_or_reparse_point
        if is_link(directory) or not directory.is_dir():
            return None
        resolved = directory.resolve()
        if not resolved.is_relative_to(directory.parent.resolve()):
            return None
        manifest = directory / "manifest.json"
        if is_link(manifest) or not manifest.is_file():
            return None
        complete = directory / "_COMPLETE"
        if require_complete and (is_link(complete) or not complete.is_file()):
            return None
        return resolved
    except (OSError, RuntimeError):
        return None


def execute_owned(
    *,
    prepared: PreparedRun,
    run_id: str,
    work: Callable[[Flight], RunResult],
    timeout: float,
    coordinator: SingleFlightCoordinator = DEFAULT_COORDINATOR,
    on_join: Callable[[dict[str, str]], None] | None = None,
) -> RunResult:
    with coordinator.claim(prepared, run_id) as flight:
        if on_join:
            on_join(flight.metadata)
        if not flight.owner:
            return flight.wait(timeout)
        try:
            result = work(flight)
        except SpecFlowError as error:
            result = RunResult(3, error_code=safe_code(error.code))
        except Exception:
            result = RunResult(3, error_code="RUNNER_FAILED")
        return flight.complete(result)
