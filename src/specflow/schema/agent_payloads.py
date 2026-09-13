"""Pydantic payload schemas for all 6 agent roles.

Each schema defines the LLM's **business output** — the structured
data the agent must return. The AgentRunner wraps this in an
``AgentExecutionResult`` envelope that carries execution metadata
(agent_id, role, model, tokens, schema_validated, etc.).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictAgentPayload(BaseModel):
    """Base contract for agent business payloads.

    Agent output is an inter-agent API.  Unknown fields must be rejected so a
    provider cannot silently change the data later stages rely on.
    """

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary", check_fields=False)
    @classmethod
    def summary_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("summary must contain non-whitespace text")
        return value


class RepositoryAnalysisPayload(StrictAgentPayload):
    """Output of the RepositoryAnalyst agent."""

    summary: str = Field(..., min_length=1, description="High-level analysis summary")
    affected_components: list[str] = Field(default_factory=list, description="Components touched")
    key_files: list[str] = Field(default_factory=list, description="Files most relevant")
    technology_notes: str = Field(default="", description="Technology stack observations")
    evidence_count: int = Field(default=0, ge=0, description="Number of evidence items found")


class DesignPayload(StrictAgentPayload):
    """Design output: include at least one nonblank architecture change,
    implementation step, API change or data-model change explanation.
    An explicit no-op must explain what is already satisfied and how to check it.
    """

    summary: str = Field(..., min_length=1, description="Design summary")
    architecture_changes: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    api_changes: list[str] = Field(default_factory=list)
    data_model_changes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def has_change_explanation(self) -> DesignPayload:
        if not any(
            item.strip()
            for items in (
                self.architecture_changes,
                self.implementation_steps,
                self.api_changes,
                self.data_model_changes,
            )
            for item in items
        ):
            raise ValueError("design requires a nonblank change or no-op explanation")
        return self


class TestStrategyPayload(StrictAgentPayload):
    """Test strategy: include at least one nonblank test scenario, edge case
    or regression check, including a check for an explicitly justified no-op.
    """

    summary: str = Field(..., min_length=1, description="Test strategy summary")
    test_scenarios: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    regression_concerns: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def has_test_intent(self) -> TestStrategyPayload:
        if not any(
            item.strip()
            for items in (self.test_scenarios, self.edge_cases, self.regression_concerns)
            for item in items
        ):
            raise ValueError("test strategy requires a nonblank scenario or check")
        return self


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
    consolidated_design: str = Field(
        ...,
        min_length=1,
        pattern=r"\S",
        description="Change explanation, or explicit no-op/information-gap rationale",
    )
    consolidated_risks: list[str] = Field(default_factory=list)
    consolidated_tests: list[str] = Field(default_factory=list)
    conflicts_resolved: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ReviewPayload(StrictAgentPayload):
    """Output of the Review agent — MUST contain a PASS/REJECT decision."""

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

    @model_validator(mode="after")
    def reject_requires_target(self) -> ReviewPayload:
        """A rejection is actionable only with an explicit revision target."""
        if self.decision == "REJECT" and not self.target_agent_id.strip():
            raise ValueError("target_agent_id is required when decision=REJECT")
        return self
