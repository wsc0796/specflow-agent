from __future__ import annotations

from dataclasses import dataclass

from specflow.agents.models import AgentConstraints, AgentDependency, AgentIdentity, RevisionPolicy


@dataclass(frozen=True)
class StructuralDelegationSpec:
    """Rule-layer source plan — before compilation. MUST NOT contain compiled fields."""

    plan_id: str
    agents: tuple[AgentIdentity, ...]
    dependencies: tuple[AgentDependency, ...]
    constraints: tuple[AgentConstraints, ...]
    revision_policy: RevisionPolicy


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
