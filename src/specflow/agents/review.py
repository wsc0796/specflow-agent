from __future__ import annotations

from typing import Any

from specflow.agents.models import AgentIdentity, AgentRole


class ReviewAgent:
    """Performs final review and issues PASS/REJECT with structured findings."""

    def __init__(self) -> None:
        self._identity = AgentIdentity(
            agent_id="review-agent-v1",
            role=AgentRole.REVIEW,
            version="1.0.0",
            description=("Performs final review and issues PASS/REJECT with structured findings"),
            prompt_id="prompts/review/v1",
            prompt_version="1.0.0",
            input_schema_id="agent/review/v1/input",
            output_schema_id="agent/review/v1/output",
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
