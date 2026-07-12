from __future__ import annotations

from dataclasses import dataclass

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
