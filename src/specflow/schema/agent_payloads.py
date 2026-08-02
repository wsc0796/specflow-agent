"""Pydantic payload schemas for all 6 agent roles.

Each schema defines the LLM's **business output** — the structured
data the agent must return. The AgentRunner wraps this in an
``AgentExecutionResult`` envelope that carries execution metadata
(agent_id, role, model, tokens, schema_validated, etc.).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from specflow.revision.models import ReviewFinding


class StrictAgentPayload(BaseModel):
    """Base contract for agent business payloads.

    Agent output is an inter-agent API.  Unknown fields must be rejected so a
    provider cannot silently change the data later stages rely on.
    """

    model_config = ConfigDict(extra="forbid")


class RepositoryAnalysisPayload(StrictAgentPayload):
    """Output of the RepositoryAnalyst agent."""

    summary: str = Field(..., min_length=1, description="High-level analysis summary")
    affected_components: list[str] = Field(default_factory=list, description="Components touched")
    key_files: list[str] = Field(default_factory=list, description="Files most relevant")
    technology_notes: str = Field(default="", description="Technology stack observations")
    evidence_count: int = Field(default=0, ge=0, description="Number of evidence items found")


class DesignPayload(StrictAgentPayload):
    """Output of the Design agent."""

    summary: str = Field(..., min_length=1, description="Design summary")
    architecture_changes: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    api_changes: list[str] = Field(default_factory=list)
    data_model_changes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class TestStrategyPayload(StrictAgentPayload):
    """Output of the TestStrategy agent."""

    summary: str = Field(..., min_length=1, description="Test strategy summary")
    test_scenarios: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    regression_concerns: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskReviewPayload(StrictAgentPayload):
    """Output of the RiskReview agent."""

    summary: str = Field(..., min_length=1, description="Risk assessment summary")
    risks: list[str] = Field(default_factory=list)
    severity: str = Field(
        default="medium", description="Overall severity: low/medium/high/critical"
    )
    migration_concerns: list[str] = Field(default_factory=list)
    rollback_plan: str = Field(default="")
    evidence_refs: list[str] = Field(default_factory=list)


class SynthesisPayload(StrictAgentPayload):
    """Output of the Synthesis agent — merges Design, TestStrategy, and RiskReview."""

    summary: str = Field(..., min_length=1, description="Merged synthesis summary")
    consolidated_design: str = Field(default="")
    consolidated_risks: list[str] = Field(default_factory=list)
    consolidated_tests: list[str] = Field(default_factory=list)
    conflicts_resolved: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ReviewPayload(StrictAgentPayload):
    """Output of the Review agent — MUST contain a PASS/REJECT decision.

    ``findings`` are structured ``ReviewFinding`` objects (never plain
    strings).  A rejection is only actionable with non-empty findings that
    name their targets, and ``requires_revision`` must agree with the
    decision.  Legacy string findings fail validation and can never be
    silently promoted into executable revision input.
    """

    schema_version: Literal["review_payload/v2"] = "review_payload/v2"

    decision: Literal["PASS", "REJECT"] = Field(
        ..., description="Final review decision — no default, must be explicit"
    )
    summary: str = Field(..., min_length=1, description="Review summary")
    findings: list[ReviewFinding] = Field(
        default_factory=list, description="Structured issues found"
    )
    severity: str = Field(default="info", description="info/warning/error/critical")
    requires_revision: bool = Field(default=False)

    @model_validator(mode="after")
    def decision_constraints(self) -> ReviewPayload:
        """Enforce the frozen PASS/REJECT consistency contract."""
        if self.decision == "REJECT":
            if not self.findings:
                raise ValueError("REJECT requires non-empty structured findings")
            if not self.requires_revision:
                raise ValueError("REJECT requires requires_revision=True")
        else:
            if self.requires_revision:
                raise ValueError("PASS cannot require revision")
        finding_ids = [finding.finding_id for finding in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("Finding IDs must be unique within a review payload")
        return self
