"""Unified run metrics for A/B comparison across legacy and multi-agent pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentMetrics:
    """Per-agent execution metrics for multi-agent mode."""

    agent_id: str
    role: str
    stage: int
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_call_success: bool = True
    fallback_used: bool = False
    degraded: bool = False
    schema_validated: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "stage": self.stage,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "llm_call_success": self.llm_call_success,
            "fallback_used": self.fallback_used,
            "degraded": self.degraded,
            "schema_validated": self.schema_validated,
        }


@dataclass
class RunMetrics:
    """Unified metrics for one pipeline run (legacy or multi-agent)."""

    mode: str  # "legacy" | "multi-agent"
    provider: str
    model: str
    status: str  # "completed" | "failed" | "degraded"

    started_at: str = ""
    completed_at: str = ""
    wall_time_ms: int = 0

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    llm_call_count: int = 0
    fallback_count: int = 0
    degraded_count: int = 0
    schema_validated_count: int = 0
    schema_unvalidated_count: int = 0

    discovered_file_count: int = 0
    selected_file_count: int = 0
    referenced_file_count: int = 0

    tool_call_count: int = 0

    revision_count: int = 0
    revision_exhausted: bool = False
    review_decision: str = ""

    # Multi-agent specific
    agent_count: int = 0
    stage_count: int = 0
    parallel_stage_count: int = 0
    handoff_count: int = 0
    agent_metrics: list[AgentMetrics] = field(default_factory=list)

    # Derived: parallel speedup (multi-agent only)
    parallel_theoretical_ms: int = 0
    parallel_actual_ms: int = 0
    parallel_speedup: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "wall_time_ms": self.wall_time_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "llm_call_count": self.llm_call_count,
            "fallback_count": self.fallback_count,
            "degraded_count": self.degraded_count,
            "schema_validated_count": self.schema_validated_count,
            "schema_unvalidated_count": self.schema_unvalidated_count,
            "discovered_file_count": self.discovered_file_count,
            "selected_file_count": self.selected_file_count,
            "referenced_file_count": self.referenced_file_count,
            "tool_call_count": self.tool_call_count,
            "revision_count": self.revision_count,
            "revision_exhausted": self.revision_exhausted,
            "review_decision": self.review_decision,
            "agent_count": self.agent_count,
            "stage_count": self.stage_count,
            "parallel_stage_count": self.parallel_stage_count,
            "handoff_count": self.handoff_count,
            "parallel_theoretical_ms": self.parallel_theoretical_ms,
            "parallel_actual_ms": self.parallel_actual_ms,
            "parallel_speedup": self.parallel_speedup,
            "agent_metrics": [a.as_dict() for a in self.agent_metrics],
        }
