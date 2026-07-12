"""Agent registry — central store for agent instances."""

from __future__ import annotations

from specflow.agents.exceptions import AgentNotFoundError, DuplicateAgentError
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.agents.protocol import Agent


class AgentRegistry:
    """Registry of Agent instances.

    Agents are keyed by ``agent_id``.  Registration, lookup, and
    role-based queries are O(1) amortised.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent: Agent) -> None:
        """Register *agent*.

        Raises ``DuplicateAgentError`` if an agent with the same
        ``agent_id`` is already registered.
        """
        if agent.agent_id in self._agents:
            raise DuplicateAgentError(f"Agent already registered: {agent.agent_id!r}")
        self._agents[agent.agent_id] = agent

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> Agent:
        """Retrieve an agent by ``agent_id``.

        Raises ``AgentNotFoundError`` if no agent with that ID exists.
        """
        try:
            return self._agents[agent_id]
        except KeyError:
            raise AgentNotFoundError(f"Agent not found: {agent_id!r}") from None

    def get_by_role(self, role: AgentRole) -> tuple[Agent, ...]:
        """Return all agents matching *role*."""
        return tuple(agent for agent in self._agents.values() if agent.role == role)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_agents(self) -> tuple[AgentIdentity, ...]:
        """Return identities of all registered agents."""
        return tuple(agent.identity for agent in self._agents.values())
