"""Tests for AgentRegistry."""

from __future__ import annotations

from typing import Any

import pytest

from specflow.agents.exceptions import AgentNotFoundError, DuplicateAgentError
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.agents.protocol import Agent
from specflow.agents.registry import AgentRegistry


class StubAgent:
    """Minimal test double implementing the Agent protocol."""

    def __init__(self, agent_id: str, role: AgentRole) -> None:
        self._agent_id = agent_id
        self._role = role
        self._identity = AgentIdentity(
            agent_id=agent_id,
            role=role,
            version="1.0.0",
            description=f"Stub agent for {role.value}",
            prompt_id="stub/v1",
            prompt_version="1.0.0",
            input_schema_id="stub/v1/input",
            output_schema_id="stub/v1/output",
        )

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def role(self) -> AgentRole:
        return self._role

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"agent_id": self._agent_id}


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def empty_registry() -> AgentRegistry:
    return AgentRegistry()


@pytest.fixture
def populated_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(StubAgent("repo-1", AgentRole.REPOSITORY_ANALYST))
    reg.register(StubAgent("design-1", AgentRole.DESIGN))
    reg.register(StubAgent("test-1", AgentRole.TEST_STRATEGY))
    reg.register(StubAgent("risk-1", AgentRole.RISK_REVIEW))
    reg.register(StubAgent("synth-1", AgentRole.SYNTHESIS))
    reg.register(StubAgent("review-1", AgentRole.REVIEW))
    return reg


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestRegister:
    def test_register_new_agent(self, empty_registry: AgentRegistry) -> None:
        agent = StubAgent("design-1", AgentRole.DESIGN)
        empty_registry.register(agent)
        assert empty_registry.get("design-1") is agent

    def test_duplicate_raises(self, empty_registry: AgentRegistry) -> None:
        agent = StubAgent("design-1", AgentRole.DESIGN)
        empty_registry.register(agent)
        with pytest.raises(DuplicateAgentError):
            empty_registry.register(StubAgent("design-1", AgentRole.DESIGN))


# ------------------------------------------------------------------
# Lookup
# ------------------------------------------------------------------


class TestGet:
    def test_get_existing(self, populated_registry: AgentRegistry) -> None:
        agent = populated_registry.get("design-1")
        assert agent.agent_id == "design-1"
        assert agent.role == AgentRole.DESIGN

    def test_get_nonexistent_raises(self, populated_registry: AgentRegistry) -> None:
        with pytest.raises(AgentNotFoundError):
            populated_registry.get("nonexistent")

    def test_get_from_empty_registry_raises(
        self, empty_registry: AgentRegistry
    ) -> None:
        with pytest.raises(AgentNotFoundError):
            empty_registry.get("any-agent")


class TestGetByRole:
    def test_matching_role(self, populated_registry: AgentRegistry) -> None:
        agents = populated_registry.get_by_role(AgentRole.DESIGN)
        assert len(agents) == 1
        assert agents[0].agent_id == "design-1"

    def test_multiple_match(self, populated_registry: AgentRegistry) -> None:
        populated_registry.register(StubAgent("design-2", AgentRole.DESIGN))
        agents = populated_registry.get_by_role(AgentRole.DESIGN)
        assert len(agents) == 2
        assert {a.agent_id for a in agents} == {"design-1", "design-2"}

    def test_no_match_returns_empty_tuple(
        self, populated_registry: AgentRegistry
    ) -> None:
        agents = populated_registry.get_by_role(AgentRole.REPOSITORY_ANALYST)
        assert len(agents) == 1

    def test_unregistered_role_returns_empty(
        self, empty_registry: AgentRegistry
    ) -> None:
        agents = empty_registry.get_by_role(AgentRole.DESIGN)
        assert agents == ()


# ------------------------------------------------------------------
# Introspection
# ------------------------------------------------------------------


class TestListAgents:
    def test_list_all(self, populated_registry: AgentRegistry) -> None:
        identities = populated_registry.list_agents()
        assert len(identities) == 6
        agent_ids = {i.agent_id for i in identities}
        assert agent_ids == {
            "repo-1",
            "design-1",
            "test-1",
            "risk-1",
            "synth-1",
            "review-1",
        }

    def test_empty_registry(self, empty_registry: AgentRegistry) -> None:
        assert empty_registry.list_agents() == ()
