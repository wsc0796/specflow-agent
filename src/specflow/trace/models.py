"""Trace System models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from specflow.agents.models import AgentRole
from specflow.plan.models import EnrichmentStatus


class TaskBriefEventType(StrEnum):
    GENERATED = "TASK_BRIEF_GENERATED"
    CONSUMED = "TASK_BRIEF_CONSUMED"


class TaskBriefTraceEvent(BaseModel):
    """Metadata-only audit event for the task brief lifecycle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: TaskBriefEventType
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    role: AgentRole
    brief_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1)
    status: EnrichmentStatus
    stage: int = Field(ge=0)
    trace_id: str = Field(min_length=1)

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


@dataclass(frozen=True)
class LLMTrace:
    """Metadata-only record for one LLM execution."""

    run_id: str
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    context_hash: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    status: str
    error_type: str | None = None
    fallback_level: str | None = None
    retry_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "context_hash": self.context_hash,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "status": self.status,
            "error_type": self.error_type,
            "fallback_level": self.fallback_level,
            "retry_count": self.retry_count,
            "metadata": dict(sorted(self.metadata.items())),
        }


@dataclass(frozen=True)
class AgentTraceSpan:
    """Timing and metadata for one agent invocation within a multi-agent trace."""

    span_id: str
    agent_id: str
    agent_role: str
    agent_version: str
    parent_span_id: str
    handoff_id: str | None = None
    stage: int = 0
    stage_started_at: str | None = None
    agent_submitted_at: str | None = None
    agent_completed_at: str | None = None
    stage_completed_at: str | None = None
    model: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    status: str = "unknown"
    fallback_level: str | None = None
    tool_calls: tuple[str, ...] = ()
    revision_round: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "agent_version": self.agent_version,
            "parent_span_id": self.parent_span_id,
            "handoff_id": self.handoff_id,
            "stage": self.stage,
            "stage_started_at": self.stage_started_at,
            "agent_submitted_at": self.agent_submitted_at,
            "agent_completed_at": self.agent_completed_at,
            "stage_completed_at": self.stage_completed_at,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "status": self.status,
            "fallback_level": self.fallback_level,
            "tool_calls": list(self.tool_calls),
            "revision_round": self.revision_round,
            "metadata": dict(sorted(self.metadata.items())),
        }
