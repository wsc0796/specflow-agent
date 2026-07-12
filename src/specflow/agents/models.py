from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from specflow.agents.exceptions import AgentModelValidationError


class AgentRole(StrEnum):
    REPOSITORY_ANALYST = "repository_analyst"
    DESIGN = "design"
    TEST_STRATEGY = "test_strategy"
    RISK_REVIEW = "risk_review"
    SYNTHESIS = "synthesis"
    REVIEW = "review"


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    role: AgentRole
    version: str
    description: str
    prompt_id: str
    prompt_version: str
    input_schema_id: str
    output_schema_id: str
    tool_permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise AgentModelValidationError("agent_id must not be empty")
        if not isinstance(self.role, AgentRole):
            raise AgentModelValidationError("role must be an AgentRole")
        if not self.version.strip():
            raise AgentModelValidationError("version must not be empty")
        if not self.description.strip():
            raise AgentModelValidationError("description must not be empty")
        if not self.prompt_id.strip():
            raise AgentModelValidationError("prompt_id must not be empty")
        if not self.prompt_version.strip():
            raise AgentModelValidationError("prompt_version must not be empty")
        if not self.input_schema_id.strip():
            raise AgentModelValidationError("input_schema_id must not be empty")
        if not self.output_schema_id.strip():
            raise AgentModelValidationError("output_schema_id must not be empty")


@dataclass(frozen=True)
class AgentDependency:
    """Logical truth source for execution order."""

    agent_id: str
    depends_on: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise AgentModelValidationError("agent_id must not be empty")
        if self.agent_id in self.depends_on:
            raise AgentModelValidationError(
                f"Agent cannot depend on itself: {self.agent_id}"
            )


@dataclass(frozen=True)
class AgentConstraints:
    agent_id: str
    max_execution_seconds: int
    max_token_budget: int
    max_revision_rounds: int = 1
    allowed_paths: tuple[str, ...] = ()
    denied_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise AgentModelValidationError("agent_id must not be empty")
        if self.max_execution_seconds <= 0:
            raise AgentModelValidationError("max_execution_seconds must be positive")
        if self.max_token_budget <= 0:
            raise AgentModelValidationError("max_token_budget must be positive")
        if self.max_revision_rounds < 0:
            raise AgentModelValidationError("max_revision_rounds must be non-negative")
        for name in ("allowed_paths", "denied_paths"):
            paths = getattr(self, name)
            if any(not p.strip() for p in paths):
                raise AgentModelValidationError(
                    f"{name} must not contain empty path strings"
                )


@dataclass(frozen=True)
class RevisionPolicy:
    max_total_rounds: int = 1
    revisable_roles: frozenset[AgentRole] = field(
        default_factory=lambda: frozenset({
            AgentRole.DESIGN,
            AgentRole.TEST_STRATEGY,
            AgentRole.RISK_REVIEW,
        })
    )
    final_authority_role: AgentRole = AgentRole.REVIEW

    def __post_init__(self) -> None:
        if self.max_total_rounds < 0:
            raise AgentModelValidationError("max_total_rounds must be non-negative")
        if not isinstance(self.final_authority_role, AgentRole):
            raise AgentModelValidationError(
                "final_authority_role must be an AgentRole"
            )

    def is_revisable(self, role: AgentRole) -> bool:
        return role in self.revisable_roles
