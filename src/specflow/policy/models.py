"""ExecutionPolicy and RunStatus models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from specflow.plan.hash_utils import canonical_json_bytes


class RunStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_DEGRADED = "completed_degraded"
    REJECTED = "rejected"
    FAILED_RUNTIME = "failed_runtime"
    FAILED_SECURITY = "failed_security"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ExecutionPolicy:
    """Unified execution limits enforced before and during a run."""

    # Wall clock
    max_wall_seconds: int = 180

    # LLM calls
    max_llm_calls: int = 10
    max_parallel_agents: int = 3

    # Revisions
    max_revisions: int = 1

    # Tokens
    max_total_tokens: int = 60000
    max_agent_input_tokens: int = 8000
    max_agent_output_tokens: int = 2000
    retry_budget_ratio: float = 0.15

    # Repository
    max_repository_files: int = 10000
    max_selected_files: int = 80
    max_evidence_chars: int = 80000

    # Tools
    max_tool_calls: int = 20

    # Behavior
    fail_on_schema_error: bool = True
    allow_degraded_completion: bool = True

    def __post_init__(self) -> None:
        if self.max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be positive")
        if self.max_llm_calls <= 0:
            raise ValueError("max_llm_calls must be positive")
        if self.max_parallel_agents <= 0:
            raise ValueError("max_parallel_agents must be positive")
        if self.max_revisions < 0:
            raise ValueError("max_revisions must be non-negative")
        if self.max_total_tokens <= 0:
            raise ValueError("max_total_tokens must be positive")
        if self.max_agent_input_tokens <= 0:
            raise ValueError("max_agent_input_tokens must be positive")
        if self.max_agent_output_tokens <= 0:
            raise ValueError("max_agent_output_tokens must be positive")
        if self.max_agent_input_tokens + self.max_agent_output_tokens > self.max_total_tokens:
            raise ValueError("agent input+output cannot exceed total token budget")
        if not 0.0 <= self.retry_budget_ratio <= 1.0:
            raise ValueError("retry_budget_ratio must be in [0.0, 1.0]")
        if self.max_repository_files <= 0:
            raise ValueError("max_repository_files must be positive")
        if self.max_selected_files <= 0:
            raise ValueError("max_selected_files must be positive")
        if self.max_evidence_chars <= 0:
            raise ValueError("max_evidence_chars must be positive")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")

    def policy_hash(self) -> str:
        data = {
            "max_wall_seconds": self.max_wall_seconds,
            "max_llm_calls": self.max_llm_calls,
            "max_parallel_agents": self.max_parallel_agents,
            "max_revisions": self.max_revisions,
            "max_total_tokens": self.max_total_tokens,
            "max_agent_input_tokens": self.max_agent_input_tokens,
            "max_agent_output_tokens": self.max_agent_output_tokens,
            "retry_budget_ratio": self.retry_budget_ratio,
            "max_repository_files": self.max_repository_files,
            "max_selected_files": self.max_selected_files,
            "max_evidence_chars": self.max_evidence_chars,
            "max_tool_calls": self.max_tool_calls,
            "fail_on_schema_error": self.fail_on_schema_error,
            "allow_degraded_completion": self.allow_degraded_completion,
        }
        return sha256(canonical_json_bytes(data)).hexdigest()
