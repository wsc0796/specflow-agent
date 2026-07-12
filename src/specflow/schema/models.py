"""Pydantic models for all 6 agents' input/output schemas.

Each agent has an input model (validates what the agent receives) and
an output model (validates what the agent produces).  The models are
intentionally minimal — they enforce structural correctness without
over-specifying content fields that the LLM may reasonably vary.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Repository Analyst ────────────────────────────────────────

class RepositoryAnalystInput(BaseModel):
    requirement: str = ""
    repository_evidence: str = ""
    repository_root: str = ""


class RepositoryAnalystOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Design ────────────────────────────────────────────────────

class DesignInput(BaseModel):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)


class DesignOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Test Strategy ─────────────────────────────────────────────

class TestStrategyInput(BaseModel):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)


class TestStrategyOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Risk Review ───────────────────────────────────────────────

class RiskReviewInput(BaseModel):
    requirement: str = ""
    repository_analysis: dict[str, Any] = Field(default_factory=dict)


class RiskReviewOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Synthesis ─────────────────────────────────────────────────

class SynthesisInput(BaseModel):
    requirement: str = ""
    design_output: dict[str, Any] = Field(default_factory=dict)
    test_strategy_output: dict[str, Any] = Field(default_factory=dict)
    risk_review_output: dict[str, Any] = Field(default_factory=dict)


class SynthesisOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any]


# ── Review ────────────────────────────────────────────────────

class ReviewInput(BaseModel):
    requirement: str = ""
    synthesis_output: dict[str, Any] = Field(default_factory=dict)


class ReviewOutput(BaseModel):
    agent_id: str
    role: str
    output: dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(default="PASS")
