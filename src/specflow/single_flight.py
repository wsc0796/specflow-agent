"""Process-local in-flight ownership; completed results are never retained."""

from __future__ import annotations

import fnmatch
import json
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
    """Int-compatible exit code with safe audit and an internal artifact locator."""

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
        result.error_code = safe_code(error_code) if error_code else None
        result.artifact_directory = artifact_directory
        result.result_status = result_status
        result.single_flight = dict(single_flight or {})
        return result

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


def artifact_result(
    code: int,
    directory: Path,
    *,
    existed: bool = False,
    require_complete: bool = False,
) -> RunResult:
    """Read only this owner's bounded manifest; never adopt an old result."""
    result = RunResult(code)
    if existed or directory.is_symlink() or not directory.is_dir():
        return result
    resolved = directory.resolve()
    if not resolved.is_relative_to(directory.parent.resolve()):
        return result
    manifest = directory / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        return result
    try:
        with manifest.open("rb") as stream:
            data = stream.read(131073)
        if len(data) > 131072:
            return result
        payload = json.loads(data)
        if not isinstance(payload, dict):
            return result
    except (OSError, ValueError):
        return result
    complete = directory / "_COMPLETE"
    can_share = not require_complete or (complete.is_file() and not complete.is_symlink())
    return RunResult(
        code,
        error_code=payload.get("error") if code == 3 else None,
        artifact_directory=resolved if can_share else None,
        result_status="rejected" if code == 0 and payload.get("revision_exhausted") else None,
    )


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
