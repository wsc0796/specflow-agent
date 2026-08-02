from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)
from specflow.plan.exceptions import PlanCompilationError, PlanValidationError


@dataclass(frozen=True)
class StructuralDelegationSpec:
    """Rule-layer source plan — before compilation. MUST NOT contain compiled fields."""

    plan_id: str
    agents: tuple[AgentIdentity, ...]
    dependencies: tuple[AgentDependency, ...]
    constraints: tuple[AgentConstraints, ...]
    revision_policy: RevisionPolicy

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise PlanCompilationError("plan_id must not be empty")
        if not self.agents:
            raise PlanCompilationError("agents must not be empty")


@dataclass(frozen=True)
class CompiledStructuralPlan:
    """Compiler output — adds execution_stages and structure_hash."""

    plan_id: str
    agents: tuple[AgentIdentity, ...]
    dependencies: tuple[AgentDependency, ...]
    execution_stages: tuple[tuple[str, ...], ...]
    constraints: tuple[AgentConstraints, ...]
    revision_policy: RevisionPolicy
    structure_hash: str

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise PlanValidationError("plan_id must not be empty")
        if not self.agents:
            raise PlanValidationError("agents must not be empty")
        if not self.structure_hash.strip():
            raise PlanValidationError("structure_hash must not be empty")
        if not self.execution_stages:
            raise PlanValidationError("execution_stages must not be empty")


TASK_BRIEF_SCHEMA_VERSION = "task_brief/v1"
TASK_BRIEF_ARTIFACT_SCHEMA_VERSION = "task_brief_artifact/v1"
CONTROLLED_EVIDENCE_SCHEMA_VERSION = "controlled-evidence/v1"


class EnrichmentStatus(StrEnum):
    """Whether a semantic brief was fully enriched or fell back to degraded defaults."""

    ENRICHED = "enriched"
    DEGRADED = "degraded"


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EvidenceReference(_StrictFrozenModel):
    """Stable pointer to evidence collected by the read-only repository boundary."""

    evidence_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    line_number: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ControlledEvidenceSummary(_StrictFrozenModel):
    """Bounded evidence text and the only evidence IDs enrichment may cite."""

    schema_version: Literal["controlled-evidence/v1"] = CONTROLLED_EVIDENCE_SCHEMA_VERSION
    content: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    references: tuple[EvidenceReference, ...] = ()
    truncated: bool = False

    @model_validator(mode="after")
    def reference_ids_are_unique(self) -> ControlledEvidenceSummary:
        ids = [reference.evidence_id for reference in self.references]
        if len(ids) != len(set(ids)):
            raise ValueError("Controlled evidence reference IDs must be unique")
        return self

    @property
    def reference_ids(self) -> frozenset[str]:
        return frozenset(reference.evidence_id for reference in self.references)


class TaskBriefEnrichmentInput(_StrictFrozenModel):
    """Code-owned, role-scoped input for one semantic enrichment request."""

    schema_version: Literal["task_brief_enrichment_input/v1"] = "task_brief_enrichment_input/v1"
    requirement: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    role: AgentRole
    role_description: str = Field(min_length=1)
    evidence_summary: ControlledEvidenceSummary
    output_schema_id: str = Field(min_length=1)
    output_schema: dict[str, Any]


class TaskBriefDraft(_StrictFrozenModel):
    """The advisory-only fields an enrichment model is allowed to produce."""

    schema_version: Literal["task_brief_draft/v1"] = "task_brief_draft/v1"
    task_description: str = Field(min_length=1)
    analysis_focus: tuple[str, ...] = ()
    evaluation_hints: tuple[str, ...] = ()
    repository_scope_hint: str = ""
    evidence_refs: tuple[str, ...] = ()

    @field_validator("analysis_focus", "evaluation_hints", "evidence_refs")
    @classmethod
    def tuple_items_must_not_be_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("Task brief list fields must not contain empty values")
        return value


class EnrichmentProvenance(_StrictFrozenModel):
    """Provenance metadata for an LLM-produced enrichment.

    Tracks the provider, model, prompt version, and request trace so that
    every enrichment can be audited and reproduced.
    """

    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    trace_id: str
    generated_at: str
    requirement_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: EnrichmentStatus
    failure_type: Literal["provider_error", "invalid_json", "schema_validation_error"] | None = None

    @field_validator("provider", "model", "prompt_id", "prompt_version", "trace_id", "generated_at")
    @classmethod
    def provenance_fields_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enrichment provenance fields must not be empty")
        return value

    @model_validator(mode="after")
    def outcome_matches_failure(self) -> EnrichmentProvenance:
        if self.outcome is EnrichmentStatus.ENRICHED and self.failure_type is not None:
            raise ValueError("Enriched provenance cannot contain failure_type")
        if self.outcome is EnrichmentStatus.DEGRADED and self.failure_type is None:
            raise ValueError("Degraded provenance requires failure_type")
        return self


class SemanticTaskBrief(_StrictFrozenModel):
    """Semantic description of what a single agent should do.

    Produced by the :class:`SemanticPlanEnricher` during the enrichment
    phase.  Carries either a full ``ENRICHED`` payload (with provenance)
    or a ``DEGRADED`` fallback when the LLM call fails.
    """

    schema_version: Literal["task_brief/v1"] = TASK_BRIEF_SCHEMA_VERSION
    agent_id: str = Field(min_length=1)
    role: AgentRole
    output_schema_id: str = Field(min_length=1)
    task_description: str = Field(min_length=1)
    analysis_focus: tuple[str, ...]
    evaluation_hints: tuple[str, ...]
    repository_scope_hint: str
    evidence_refs: tuple[EvidenceReference, ...] = ()
    status: EnrichmentStatus = Field(validation_alias=AliasChoices("status", "enrichment_status"))
    provenance: EnrichmentProvenance

    @field_validator("analysis_focus", "evaluation_hints")
    @classmethod
    def semantic_list_items_must_not_be_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("Task brief list fields must not contain empty values")
        return value

    @model_validator(mode="after")
    def status_matches_provenance(self) -> SemanticTaskBrief:
        if self.status is not self.provenance.outcome:
            raise ValueError("Task brief status must match provenance outcome")
        return self

    @property
    def enrichment_status(self) -> EnrichmentStatus:
        """Compatibility accessor for callers predating the v1 execution contract."""
        return self.status

    def execution_payload(self) -> dict[str, Any]:
        """Return only fields allowed to influence worker execution."""
        return self.model_dump(mode="json", exclude={"provenance"})

    def brief_hash(self) -> str:
        from specflow.plan.hash_utils import canonical_json_bytes

        return sha256(canonical_json_bytes(self.execution_payload())).hexdigest()

    @classmethod
    def degraded_default(
        cls,
        *,
        agent_id: str,
        role: AgentRole,
        output_schema_id: str,
        task_description: str,
        provenance: EnrichmentProvenance,
        analysis_focus: tuple[str, ...] = (),
        evaluation_hints: tuple[str, ...] = (),
        repository_scope_hint: str = "",
    ) -> SemanticTaskBrief:
        """Create a degraded brief — used when the LLM enrichment call fails."""
        return cls(
            agent_id=agent_id,
            role=role,
            output_schema_id=output_schema_id,
            task_description=task_description,
            analysis_focus=analysis_focus,
            evaluation_hints=evaluation_hints,
            repository_scope_hint=repository_scope_hint,
            evidence_refs=(),
            status=EnrichmentStatus.DEGRADED,
            provenance=provenance,
        )


class TaskBriefArtifact(_StrictFrozenModel):
    """Versioned, self-verifying artifact containing all normalized task briefs."""

    schema_version: Literal["task_brief_artifact/v1"] = TASK_BRIEF_ARTIFACT_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    briefs: tuple[SemanticTaskBrief, ...]
    brief_hashes: dict[str, str]
    canonical_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_count: int = Field(ge=1)
    enriched_agents: tuple[str, ...]
    degraded_agents: tuple[str, ...]

    @classmethod
    def build(cls, run_id: str, briefs: tuple[SemanticTaskBrief, ...]) -> TaskBriefArtifact:
        if not briefs:
            raise ValueError("TaskBriefArtifact requires at least one brief")
        brief_hashes = {brief.agent_id: brief.brief_hash() for brief in briefs}
        if len(brief_hashes) != len(briefs):
            raise ValueError("TaskBriefArtifact agent IDs must be unique")
        data: dict[str, Any] = {
            "schema_version": TASK_BRIEF_ARTIFACT_SCHEMA_VERSION,
            "run_id": run_id,
            "briefs": briefs,
            "brief_hashes": brief_hashes,
            "generated_count": len(briefs),
            "enriched_agents": tuple(
                brief.agent_id for brief in briefs if brief.status is EnrichmentStatus.ENRICHED
            ),
            "degraded_agents": tuple(
                brief.agent_id for brief in briefs if brief.status is EnrichmentStatus.DEGRADED
            ),
        }
        from specflow.plan.hash_utils import canonical_json_bytes

        hash_payload = cls._hash_payload_from_data(data)
        data["canonical_hash"] = sha256(canonical_json_bytes(hash_payload)).hexdigest()
        return cls.model_validate(data)

    def hash_payload(self) -> dict[str, Any]:
        return self._hash_payload_from_data(
            self.model_dump(mode="json", exclude={"canonical_hash"})
        )

    @staticmethod
    def _hash_payload_from_data(data: dict[str, Any]) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, BaseModel):
                return value.model_dump(mode="json")
            if isinstance(value, tuple):
                return [normalize(item) for item in value]
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, dict):
                return {str(key): normalize(item) for key, item in value.items()}
            return value

        return normalize(data)

    @model_validator(mode="after")
    def artifact_is_consistent(self) -> TaskBriefArtifact:
        from specflow.plan.hash_utils import canonical_json_bytes

        if self.generated_count != len(self.briefs):
            raise ValueError("TaskBriefArtifact generated_count is inconsistent")
        if set(self.brief_hashes) != {brief.agent_id for brief in self.briefs}:
            raise ValueError("TaskBriefArtifact brief_hashes are inconsistent")
        expected_enriched = tuple(
            brief.agent_id for brief in self.briefs if brief.status is EnrichmentStatus.ENRICHED
        )
        expected_degraded = tuple(
            brief.agent_id for brief in self.briefs if brief.status is EnrichmentStatus.DEGRADED
        )
        if self.enriched_agents != expected_enriched or self.degraded_agents != expected_degraded:
            raise ValueError("TaskBriefArtifact status indexes are inconsistent")
        for brief in self.briefs:
            if self.brief_hashes[brief.agent_id] != brief.brief_hash():
                raise ValueError("TaskBriefArtifact contains an invalid brief hash")
        expected = sha256(canonical_json_bytes(self.hash_payload())).hexdigest()
        if self.canonical_hash != expected:
            raise ValueError("TaskBriefArtifact canonical hash is invalid")
        return self


@dataclass(frozen=True)
class AgentTask:
    """A single agent's task within an effective delegation plan.

    Binds an :class:`AgentIdentity`-equivalent to its :class:`SemanticTaskBrief`,
    execution stage, and constraints.  The ``enriched`` property is derived
    from the brief — it is NOT an independent stored field.
    """

    agent_id: str
    role: AgentRole
    stage: int
    depends_on: frozenset[str]
    constraints: AgentConstraints
    task_brief: SemanticTaskBrief

    @property
    def enriched(self) -> bool:
        """Derived — ``True`` if the task brief was fully enriched."""
        return self.task_brief.enrichment_status is EnrichmentStatus.ENRICHED


@dataclass(frozen=True)
class EffectiveDelegationPlan:
    """The executable plan combining structural and semantic layers.

    Carries all hashes needed for reproducibility and auditing.  The
    ``degraded_agents`` and ``enriched`` properties are derived from the
    tasks — they are NOT independent stored fields.
    """

    plan_id: str
    run_id: str
    structure_hash: str
    semantic_brief_hash: str
    effective_plan_hash: str
    stages: tuple[tuple[str, ...], ...]
    tasks: tuple[AgentTask, ...]
    revision_policy: RevisionPolicy
    generated_at: str

    @property
    def degraded_agents(self) -> tuple[str, ...]:
        """Agent IDs whose task briefs are degraded (not enriched)."""
        return tuple(t.agent_id for t in self.tasks if not t.enriched)

    @property
    def enriched(self) -> bool:
        """Derived — ``True`` when *all* task briefs are enriched."""
        return len(self.degraded_agents) == 0
