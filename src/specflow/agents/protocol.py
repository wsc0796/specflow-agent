"""Agent protocol — structural typing for agent implementations."""

from __future__ import annotations

from typing import Any, Protocol

from specflow.agents.models import AgentIdentity, AgentRole


class Agent(Protocol):
    """Structural typing protocol for any agent implementation.

    An agent is identified by a unique ID and role, carries an identity
    descriptor, and can execute work given a context dictionary.
    """

    @property
    def agent_id(self) -> str:
        """Unique identifier for this agent instance."""

    @property
    def role(self) -> AgentRole:
        """The domain role this agent fulfills."""

    @property
    def identity(self) -> AgentIdentity:
        """Full identity descriptor including version and schemas."""

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task given *context* and return results."""
