"""Pydantic payload schemas for all 6 agent roles.

Each schema defines the LLM's **business output** — the structured
data the agent must return. The AgentRunner wraps this in an
``AgentExecutionResult`` envelope that carries execution metadata
(agent_id, role, model, tokens, schema_validated, etc.).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepositoryAnalysisPayload(BaseModel):
    """Output of the RepositoryAnalyst agent."""

    model_config = ConfigDict(extra="allow")

    summary: str = Field(..., min_length=1, description="High-level analysis summary")
    affected_components: list[str] = Field(default_factory=list, description="Components touched")
    key_files: list[str] = Field(default_factory=list, description="Files most relevant")
    technology_notes: str = Field(default="", description="Technology stack observations")
    evidence_count: int = Field(default=0, ge=0, description="Number of evidence items found")


class DesignPayload(BaseModel):
    """Output of the Design agent."""

    model_config = ConfigDict(extra="allow")

    summary: str = Field(..., min_length=1, description="Design summary")
    architecture_changes: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    api_changes: list[str] = Field(default_factory=list)
    data_model_changes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class TestStrategyPayload(BaseModel):
    """Output of the TestStrategy agent."""

    model_config = ConfigDict(extra="allow")

    summary: str = Field(..., min_length=1, description="Test strategy summary")
    test_scenarios: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    regression_concerns: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskReviewPayload(BaseModel):
    """Output of the RiskReview agent."""

    model_config = ConfigDict(extra="allow")

    summary: str = Field(..., min_length=1, description="Risk assessment summary")
    risks: list[str] = Field(default_factory=list)
    severity: str = Field(
        default="medium", description="Overall severity: low/medium/high/critical"
    )
    migration_concerns: list[str] = Field(default_factory=list)
    rollback_plan: str = Field(default="")
    evidence_refs: list[str] = Field(default_factory=list)


class SynthesisPayload(BaseModel):
    """Output of the Synthesis agent — merges Design, TestStrategy, and RiskReview."""

    model_config = ConfigDict(extra="allow")

    summary: str = Field(..., min_length=1, description="Merged synthesis summary")
    consolidated_design: str = Field(default="")
    consolidated_risks: list[str] = Field(default_factory=list)
    consolidated_tests: list[str] = Field(default_factory=list)
    conflicts_resolved: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ReviewPayload(BaseModel):
    """Output of the Review agent — MUST contain a PASS/REJECT decision."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["PASS", "REJECT"] = Field(
        ..., description="Final review decision — no default, must be explicit"
    )
    summary: str = Field(..., min_length=1, description="Review summary")
    findings: list[str] = Field(default_factory=list, description="Issues found")
    severity: str = Field(default="info", description="info/warning/error/critical")
    requires_revision: bool = Field(default=False)
    target_agent_id: str = Field(
        default="",
        description="Agent that must revise (required when decision=REJECT)",
    )
