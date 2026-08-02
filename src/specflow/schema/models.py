"""Pydantic models for all 6 agents' input/output schemas.

Each agent has an input model (validates what the agent receives) and
an output model (validates what the agent produces).  The models are
intentionally minimal — they enforce structural correctness without
over-specifying content fields that the LLM may reasonably vary.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from specflow.agents.models import AgentRole
from specflow.plan.models import ControlledEvidenceSummary, SemanticTaskBrief
from specflow.revision.models import RevisionContext


class StrictAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentExecutionInput(BaseModel):
    """Strict, role-scoped envelope consumed by the multi-agent LLM adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["agent-execution-input/v1"] = "agent-execution-input/v1"
    run_id: str = Field(min_length=1)
    stage: int = Field(ge=0)
    agent_id: str = Field(min_length=1)
    role: AgentRole
    requirement: str = Field(min_length=1)
    evidence_summary: ControlledEvidenceSummary
    repository_analysis: dict[str, Any] | None = None
    task_brief: SemanticTaskBrief
    prior_outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    revision_context: RevisionContext | None = None
    output_schema_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def identity_and_evidence_must_match(self) -> AgentExecutionInput:
        brief = self.task_brief
        if brief.agent_id != self.agent_id:
            raise ValueError("Task brief agent_id does not match execution agent_id")
        if brief.role is not self.role:
            raise ValueError("Task brief role does not match execution role")
        if brief.output_schema_id != self.output_schema_id:
            raise ValueError("Task brief output schema does not match execution output schema")
        unknown_refs = {
            reference.evidence_id for reference in brief.evidence_refs
        } - self.evidence_summary.reference_ids
        if unknown_refs:
            raise ValueError("Task brief contains unknown evidence references")
        if (
            self.revision_context is not None
            and self.revision_context.target_agent_id != self.agent_id
        ):
            raise ValueError("Revision context target does not match execution agent")
        return self


# ── Repository Analyst ────────────────────────────────────────


class RepositoryAnalystInput(StrictAgentInput):
    requirement: str = ""
    repository_evidence: str = ""
    repository_root: str = ""


class RepositoryAnalystOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Design ────────────────────────────────────────────────────


class DesignInput(StrictAgentInput):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)


class DesignOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Test Strategy ─────────────────────────────────────────────


class TestStrategyInput(StrictAgentInput):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)


class TestStrategyOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Risk Review ───────────────────────────────────────────────


class RiskReviewInput(StrictAgentInput):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)


class RiskReviewOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Synthesis ─────────────────────────────────────────────────


class SynthesisInput(StrictAgentInput):
    requirement: str = ""
    design_output: dict[str, Any] = Field(default_factory=dict)
    test_strategy_output: dict[str, Any] = Field(default_factory=dict)
    risk_review_output: dict[str, Any] = Field(default_factory=dict)


class SynthesisOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Review ────────────────────────────────────────────────────


class ReviewInput(StrictAgentInput):
    requirement: str = ""
    synthesis_output: dict[str, Any] = Field(default_factory=dict)


class ReviewOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(default="")
