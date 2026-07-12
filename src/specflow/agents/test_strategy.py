from __future__ import annotations

from typing import Any

from specflow.agents.models import AgentIdentity, AgentRole


class TestStrategyAgent:
    """Independently generates comprehensive test strategies."""

    def __init__(self) -> None:
        self._identity = AgentIdentity(
            agent_id="test-strategy-agent-v1",
            role=AgentRole.TEST_STRATEGY,
            version="1.0.0",
            description=(
                "Independently generates comprehensive test strategies"
            ),
            prompt_id="prompts/test-strategy/v1",
            prompt_version="1.0.0",
            input_schema_id="agent/test-strategy/v1/input",
            output_schema_id="agent/test-strategy/v1/output",
            tool_permissions=frozenset({"list_files", "search_code", "read_file"}),
        )

    @property
    def agent_id(self) -> str:
        return self._identity.agent_id

    @property
    def role(self) -> AgentRole:
        return self._identity.role

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "role": self.role.value, "output": {}}
