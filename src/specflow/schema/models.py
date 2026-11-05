"""Pydantic models for all 6 agents' input/output schemas.

Each agent has an input model (validates what the agent receives) and
an output model (validates what the agent produces).  The models are
intentionally minimal — they enforce structural correctness without
over-specifying content fields that the LLM may reasonably vary.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RevisionFeedback(StrictAgentInput):
    """Validated review data delivered only to the selected revision target."""

    target_agent_id: str = Field(min_length=1, pattern=r"\S")
    round_number: int = Field(ge=1)
    summary: str = Field(min_length=1, pattern=r"\S")
    findings: list[str] = Field(default_factory=list)


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
    revision_feedback: RevisionFeedback | None = None


class DesignOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Test Strategy ─────────────────────────────────────────────


class TestStrategyInput(StrictAgentInput):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)
    revision_feedback: RevisionFeedback | None = None


class TestStrategyOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Risk Review ───────────────────────────────────────────────


class RiskReviewInput(StrictAgentInput):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)
    revision_feedback: RevisionFeedback | None = None


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
