"""Strict contracts for finding-driven revision.

Phase 2 replaces the revision-replay path with a real data chain:

``ReviewFinding`` -> ``RevisionInput`` -> target agent revision request ->
``FindingResolution`` -> re-review.

Every model is strict (``extra="forbid"``), frozen where it is an execution
contract, versioned, and self-consistent.  Legacy string findings are never
silently promoted into executable findings.
"""

from __future__ import annotations

import re
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from specflow.agents.models import AgentRole
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.plan.models import ControlledEvidenceSummary, SemanticTaskBrief


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


def derive_finding_id(
    *,
    target_agent_id: str,
    category: str,
    description: str,
    affected_artifact: str | None,
    evidence_refs: tuple[str, ...],
) -> str:
    """Derive a stable finding ID from normalized finding content.

    Uses the project's single canonical-JSON hash helper, so identical
    normalized findings always produce the same ID.  The ``F-`` prefix keeps
    finding IDs visually distinct from revision IDs.
    """
    normalized_description = re.sub(r"\s+", " ", description).strip().casefold()
    payload = {
        "target_agent_id": target_agent_id,
        "category": category.strip().casefold(),
        "description": normalized_description,
        "affected_artifact": affected_artifact,
        "evidence_refs": sorted(evidence_refs),
    }
    digest = sha256(canonical_json_bytes(payload)).hexdigest()
    return f"F-{digest[:8]}"


class ReviewFinding(_StrictFrozenModel):
    """One structured, addressable issue produced by the reviewer."""

    schema_version: Literal["review_finding/v1"] = "review_finding/v1"
    finding_id: str = Field(min_length=1, pattern=r"^F-[0-9a-f]{8}$")
    severity: FindingSeverity
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    affected_artifact: str | None = None
    evidence_refs: tuple[str, ...] = ()
    recommendation: str = Field(min_length=1)

    @field_validator("category", "description", "recommendation")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Finding text fields must not be empty")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def evidence_refs_non_empty_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("Finding evidence_refs must not contain empty values")
        return value


class ValidatedAgentOutput(_StrictFrozenModel):
    """A previously validated agent output referenced by revision."""

    agent_id: str = Field(min_length=1)
    schema_id: str = Field(min_length=1)
    payload: dict[str, Any]


class RevisionInput(_StrictFrozenModel):
    """Complete, frozen input for one targeted revision of one agent."""

    schema_version: Literal["revision_input/v1"] = "revision_input/v1"
    run_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    revision_round: int = Field(ge=1)
    max_revision_rounds: int = Field(ge=1)
    target_agent_id: str = Field(min_length=1)
    role: AgentRole
    original_requirement: str = Field(min_length=1)
    verified_evidence: ControlledEvidenceSummary
    task_brief: SemanticTaskBrief
    prior_output: ValidatedAgentOutput
    prior_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: tuple[ReviewFinding, ...]
    output_schema_id: str = Field(min_length=1)

    @classmethod
    def build(
        cls,
        *,
        run_id: str,
        revision_id: str,
        revision_round: int,
        max_revision_rounds: int,
        target_agent_id: str,
        role: AgentRole,
        original_requirement: str,
        verified_evidence: ControlledEvidenceSummary,
        task_brief: SemanticTaskBrief,
        prior_output: ValidatedAgentOutput,
        findings: tuple[ReviewFinding, ...],
        output_schema_id: str,
    ) -> RevisionInput:
        """Build a revision input, deriving and verifying the prior-output hash."""
        prior_output_hash = sha256(canonical_json_bytes(prior_output.payload)).hexdigest()
        return cls(
            run_id=run_id,
            revision_id=revision_id,
            revision_round=revision_round,
            max_revision_rounds=max_revision_rounds,
            target_agent_id=target_agent_id,
            role=role,
            original_requirement=original_requirement,
            verified_evidence=verified_evidence,
            task_brief=task_brief,
            prior_output=prior_output,
            prior_output_hash=prior_output_hash,
            findings=findings,
            output_schema_id=output_schema_id,
        )

    @model_validator(mode="after")
    def revision_input_is_consistent(self) -> RevisionInput:
        if self.revision_round > self.max_revision_rounds:
            raise ValueError("revision_round cannot exceed max_revision_rounds")
        if self.task_brief.agent_id != self.target_agent_id:
            raise ValueError("Task brief agent does not match revision target")
        if self.task_brief.output_schema_id != self.output_schema_id:
            raise ValueError("Task brief output schema does not match revision output schema")
        if self.prior_output.agent_id != self.target_agent_id:
            raise ValueError("Prior output agent does not match revision target")
        unknown_targets = {finding.target_agent_id for finding in self.findings} - {
            self.target_agent_id
        }
        if unknown_targets:
            raise ValueError("Revision findings must target the revised agent")
        computed_hash = sha256(canonical_json_bytes(self.prior_output.payload)).hexdigest()
        if self.prior_output_hash != computed_hash:
            raise ValueError("prior_output_hash does not match prior output")
        return self


class RevisionContext(_StrictFrozenModel):
    """Execution-scoped revision state carried inside ``AgentExecutionInput``."""

    schema_version: Literal["revision_context/v1"] = "revision_context/v1"
    revision_id: str = Field(min_length=1)
    revision_round: int = Field(ge=1)
    max_revision_rounds: int = Field(ge=1)
    target_agent_id: str = Field(min_length=1)
    prior_output: ValidatedAgentOutput
    prior_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: tuple[ReviewFinding, ...]
    parent_artifact: str | None = None
    review_artifact_hash: str | None = None

    @model_validator(mode="after")
    def revision_context_is_consistent(self) -> RevisionContext:
        if self.prior_output.agent_id != self.target_agent_id:
            raise ValueError("Revision prior output does not match target agent")
        computed_hash = sha256(canonical_json_bytes(self.prior_output.payload)).hexdigest()
        if self.prior_output_hash != computed_hash:
            raise ValueError("prior_output_hash does not match prior output")
        return self


class FindingResolution(_StrictFrozenModel):
    """The target agent's disposition of exactly one input finding."""

    schema_version: Literal["finding_resolution/v1"] = "finding_resolution/v1"
    finding_id: str = Field(min_length=1, pattern=r"^F-[0-9a-f]{8}$")
    status: ResolutionStatus
    explanation: str = Field(min_length=1)
    changed_sections: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @field_validator("explanation")
    @classmethod
    def explanation_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Finding resolution explanation must not be empty")
        return value


class RevisionResult(_StrictFrozenModel):
    """Outcome of one revision execution: revised output plus resolutions."""

    schema_version: Literal["revision_result/v1"] = "revision_result/v1"
    revision_id: str = Field(min_length=1)
    revision_round: int = Field(ge=1)
    parent_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    revised_output: ValidatedAgentOutput
    resolutions: tuple[FindingResolution, ...]
    unresolved_finding_ids: tuple[str, ...]

    @classmethod
    def build(
        cls,
        *,
        revision_id: str,
        revision_round: int,
        parent_output_hash: str,
        revised_output: ValidatedAgentOutput,
        input_finding_ids: tuple[str, ...],
        resolutions: tuple[FindingResolution, ...],
    ) -> RevisionResult:
        """Build a result, enforcing that resolutions exactly match input findings."""
        resolved_ids = {resolution.finding_id for resolution in resolutions}
        if len(resolved_ids) != len(resolutions):
            raise ValueError("Finding resolution IDs must be unique")
        if resolved_ids != set(input_finding_ids):
            raise ValueError("Resolutions must exactly cover the input findings")
        unresolved_ids = tuple(
            resolution.finding_id
            for resolution in sorted(resolutions, key=lambda r: r.finding_id)
            if resolution.status is ResolutionStatus.UNRESOLVED
        )
        return cls(
            revision_id=revision_id,
            revision_round=revision_round,
            parent_output_hash=parent_output_hash,
            revised_output=revised_output,
            resolutions=resolutions,
            unresolved_finding_ids=unresolved_ids,
        )

    @model_validator(mode="after")
    def unresolved_ids_match_resolutions(self) -> RevisionResult:
        expected = tuple(
            resolution.finding_id
            for resolution in sorted(self.resolutions, key=lambda r: r.finding_id)
            if resolution.status is ResolutionStatus.UNRESOLVED
        )
        if self.unresolved_finding_ids != expected:
            raise ValueError("unresolved_finding_ids must match unresolved resolutions")
        return self
