from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from specflow.agents.models import AgentConstraints, AgentDependency, AgentIdentity, RevisionPolicy
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


class EnrichmentStatus(Enum):
    """Whether a semantic brief was fully enriched or fell back to degraded defaults."""

    ENRICHED = "enriched"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class EnrichmentProvenance:
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

    def __post_init__(self) -> None:
        for field_name in (
            "provider", "model", "prompt_id", "prompt_version",
            "trace_id", "generated_at",
        ):
            if not getattr(self, field_name).strip():
                raise PlanValidationError(f"{field_name} must not be empty")


@dataclass(frozen=True)
class SemanticTaskBrief:
    """Semantic description of what a single agent should do.

    Produced by the :class:`SemanticPlanEnricher` during the enrichment
    phase.  Carries either a full ``ENRICHED`` payload (with provenance)
    or a ``DEGRADED`` fallback when the LLM call fails.
    """

    agent_id: str
    task_description: str
    analysis_focus: tuple[str, ...]
    evaluation_hints: tuple[str, ...]
    repository_scope_hint: str
    enrichment_status: EnrichmentStatus
    provenance: EnrichmentProvenance | None

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must not be empty")
        if not isinstance(self.enrichment_status, EnrichmentStatus):
            raise ValueError("enrichment_status must be an EnrichmentStatus")

    @classmethod
    def degraded_default(
        cls,
        *,
        agent_id: str,
        task_description: str,
        analysis_focus: tuple[str, ...] = (),
        evaluation_hints: tuple[str, ...] = (),
        repository_scope_hint: str = "",
    ) -> SemanticTaskBrief:
        """Create a degraded brief — used when the LLM enrichment call fails."""
        return cls(
            agent_id=agent_id,
            task_description=task_description,
            analysis_focus=analysis_focus,
            evaluation_hints=evaluation_hints,
            repository_scope_hint=repository_scope_hint,
            enrichment_status=EnrichmentStatus.DEGRADED,
            provenance=None,
        )
