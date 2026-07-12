"""Execution policy, error taxonomy, and run outcome models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from hashlib import sha256

from specflow.plan.hash_utils import canonical_json_bytes

# ── Run Status ───────────────────────────────────────────────────


class RunStatus:
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_DEGRADED = "completed_degraded"
    REJECTED = "rejected"
    FAILED_RUNTIME = "failed_runtime"
    FAILED_SECURITY = "failed_security"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"


# ── Sub-policies ─────────────────────────────────────────────────


@dataclass(frozen=True)
class RepositoryPolicy:
    max_scanned_files: int = 10000
    max_selected_files: int = 80
    max_file_bytes: int = 262144
    max_total_evidence_chars: int = 80000
    max_evidence_items: int = 200

    def __post_init__(self) -> None:
        _check_positive(self, "max_scanned_files")
        _check_positive(self, "max_selected_files")
        _check_positive(self, "max_file_bytes")
        _check_positive(self, "max_total_evidence_chars")
        _check_positive(self, "max_evidence_items")
        if self.max_selected_files > self.max_scanned_files:
            raise ValueError("max_selected_files must not exceed max_scanned_files")


@dataclass(frozen=True)
class TokenPolicy:
    max_run_input_tokens: int = 50000
    max_run_output_tokens: int = 12000
    max_run_total_tokens: int = 62000
    max_agent_input_tokens: int = 10000
    max_agent_output_tokens: int = 3000
    reserved_retry_tokens: int = 6000

    def __post_init__(self) -> None:
        for name in (
            "max_run_input_tokens",
            "max_run_output_tokens",
            "max_run_total_tokens",
            "max_agent_input_tokens",
            "max_agent_output_tokens",
        ):
            _check_positive(self, name)
        _check_non_negative(self, "reserved_retry_tokens")
        if self.reserved_retry_tokens >= self.max_run_total_tokens:
            raise ValueError("reserved_retry_tokens must be less than max_run_total_tokens")


@dataclass(frozen=True)
class RetryPolicy:
    max_provider_retries: int = 2
    max_schema_retries: int = 1
    max_json_repair_attempts: int = 1

    def __post_init__(self) -> None:
        _check_non_negative(self, "max_provider_retries")
        _check_non_negative(self, "max_schema_retries")
        _check_non_negative(self, "max_json_repair_attempts")


@dataclass(frozen=True)
class ArtifactPolicy:
    max_artifact_bytes: int = 5 * 1024 * 1024
    max_error_message_chars: int = 500
    include_raw_provider_output: bool = False
    include_raw_prompt: bool = False

    def __post_init__(self) -> None:
        _check_positive(self, "max_artifact_bytes")
        _check_positive(self, "max_error_message_chars")


# ── Composite ExecutionPolicy ────────────────────────────────────


@dataclass(frozen=True)
class ExecutionPolicy:
    """Top-level execution policy composing all sub-policies."""

    policy_version: str = "1.0.0"
    max_wall_time_seconds: int = 300
    max_llm_calls: int = 10
    max_parallel_agents: int = 3
    max_revisions: int = 1
    fail_on_schema_error: bool = True
    allow_degraded_completion: bool = True

    repository: RepositoryPolicy = field(default_factory=RepositoryPolicy)
    tokens: TokenPolicy = field(default_factory=TokenPolicy)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    artifacts: ArtifactPolicy = field(default_factory=ArtifactPolicy)

    def __post_init__(self) -> None:
        if self.max_wall_time_seconds <= 0:
            raise ValueError("max_wall_time_seconds must be positive")
        _check_positive(self, "max_llm_calls")
        _check_positive(self, "max_parallel_agents")
        if self.max_revisions < 0:
            raise ValueError("max_revisions must be non-negative")

    def policy_hash(self) -> str:
        data: dict[str, object] = {
            "policy_version": self.policy_version,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "max_llm_calls": self.max_llm_calls,
            "max_parallel_agents": self.max_parallel_agents,
            "max_revisions": self.max_revisions,
            "fail_on_schema_error": self.fail_on_schema_error,
            "allow_degraded_completion": self.allow_degraded_completion,
            "repository": {
                "max_scanned_files": self.repository.max_scanned_files,
                "max_selected_files": self.repository.max_selected_files,
                "max_file_bytes": self.repository.max_file_bytes,
                "max_total_evidence_chars": self.repository.max_total_evidence_chars,
                "max_evidence_items": self.repository.max_evidence_items,
            },
            "tokens": {
                "max_run_input_tokens": self.tokens.max_run_input_tokens,
                "max_run_output_tokens": self.tokens.max_run_output_tokens,
                "max_run_total_tokens": self.tokens.max_run_total_tokens,
                "max_agent_input_tokens": self.tokens.max_agent_input_tokens,
                "max_agent_output_tokens": self.tokens.max_agent_output_tokens,
                "reserved_retry_tokens": self.tokens.reserved_retry_tokens,
            },
            "retry": {
                "max_provider_retries": self.retry.max_provider_retries,
                "max_schema_retries": self.retry.max_schema_retries,
                "max_json_repair_attempts": self.retry.max_json_repair_attempts,
            },
            "artifacts": {
                "max_artifact_bytes": self.artifacts.max_artifact_bytes,
                "max_error_message_chars": self.artifacts.max_error_message_chars,
                "include_raw_provider_output": self.artifacts.include_raw_provider_output,
                "include_raw_prompt": self.artifacts.include_raw_prompt,
            },
        }
        return sha256(canonical_json_bytes(data)).hexdigest()


# ── SpecFlowError ────────────────────────────────────────────────


@dataclass
class SpecFlowError(Exception):
    """Safe, auditable error that never leaks raw exception data to artifacts."""

    code: str
    safe_message: str
    retryable: bool = False
    stage: str = ""
    agent_id: str = ""
    internal_error_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.safe_message)
        # details must never contain sensitive values
        safe_details: dict[str, object] = {}
        for k, v in self.details.items():
            safe_details[k] = _sanitize_detail(v)
        object.__setattr__(self, "details", safe_details)


# ── RunOutcome ───────────────────────────────────────────────────


@dataclass(frozen=True)
class RunOutcome:
    status: str
    error_code: str = ""
    safe_message: str = ""
    requires_review: bool = False
    degraded: bool = False
    retryable: bool = False
    failed_stage: str = ""
    failed_agent_id: str = ""

    def __post_init__(self) -> None:
        if self.status == RunStatus.REJECTED and self.error_code:
            pass  # business rejection is not a runtime error
        if self.status == RunStatus.FAILED_SECURITY and not self.error_code:
            raise ValueError("FAILED_SECURITY requires an error_code")


# ── Helpers ──────────────────────────────────────────────────────


def _check_positive(obj: object, field_name: str) -> None:
    value = getattr(obj, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _check_non_negative(obj: object, field_name: str) -> None:
    value = getattr(obj, field_name)
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _sanitize_detail(value: object) -> object:
    if isinstance(value, str):
        lower = value.lower()
        for keyword in ("api_key", "token", "secret", "password", "authorization", "bearer"):
            if keyword in lower:
                return "[REDACTED]"
    return value
