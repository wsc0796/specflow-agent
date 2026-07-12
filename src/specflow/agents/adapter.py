"""Agent Runner — bridges Agent identity to LLM execution."""

from __future__ import annotations

import json
from typing import Any

from specflow.agents.models import AgentIdentity
from specflow.llm.client import LLMClient
from specflow.llm.models import LLMMessage, LLMRequest


class AgentRunner:
    """Wraps an Agent identity with LLM-backed execution.

    Does NOT modify the agent — it wraps the agent's identity and
    provides a callable ``execute(context)`` that goes through the
    real LLM provider.

    On failure, returns a degraded result instead of raising.
    """

    def __init__(
        self,
        identity: AgentIdentity,
        llm_client: LLMClient,
        *,
        system_prompt: str = "",
        model: str = "unknown",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> None:
        self._identity = identity
        self._llm = llm_client
        self._system_prompt = system_prompt
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def agent_id(self) -> str:
        return self._identity.agent_id

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Call the LLM and return structured output.

        Merges *context* into the user message and expects JSON back.
        On any failure returns a degraded result — never raises.
        """
        requirement = context.get("requirement", "")
        prior_outputs = context.get("prior_outputs", {})
        task_description = context.get("task_description", self._identity.description)
        evidence = context.get("repository_evidence", "")

        user_message = _build_user_message(
            role=self._identity.role.value,
            task_description=task_description,
            requirement=requirement,
            prior_outputs=prior_outputs,
            evidence=evidence,
        )

        try:
            messages: list[LLMMessage] = []
            if self._system_prompt.strip():
                messages.append(LLMMessage(role="system", content=self._system_prompt))
            messages.append(LLMMessage(role="user", content=user_message))

            response = self._llm.complete(
                LLMRequest(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                    response_format="json",
                )
            )
            data = json.loads(response.content)
            return {
                "agent_id": self.agent_id,
                "role": self._identity.role.value,
                "success": True,
                "output": data,
                "model": self._model,
                "usage": {
                    "input_tokens": getattr(response, "input_tokens", 0),
                    "output_tokens": getattr(response, "output_tokens", 0),
                },
            }
        except Exception as exc:
            return {
                "agent_id": self.agent_id,
                "role": self._identity.role.value,
                "success": False,
                "error": str(exc),
                "degraded": True,
            }


def _build_user_message(
    role: str,
    task_description: str,
    requirement: str,
    prior_outputs: dict[str, Any],
    evidence: str = "",
) -> str:
    """Build a structured user message for one agent execution."""
    parts: list[str] = [
        f"You are the **{role}** agent in a multi-agent specification pipeline.",
        "",
        "## Task",
        task_description,
    ]
    if requirement:
        parts.extend(["", "## Requirement", requirement])
    if evidence.strip():
        parts.extend(["", "## Repository Evidence", evidence])
    if prior_outputs:
        parts.append("")
        parts.append("## Context from Previous Agents")
        for agent_id, output in prior_outputs.items():
            summary = _summarize_output(output)
            parts.append(f"### {agent_id}")
            parts.append(summary)

    parts.extend(["", "Return a JSON object with your structured analysis."])
    return "\n".join(parts)


def _summarize_output(output: dict[str, Any], max_chars: int = 500) -> str:
    """Truncate agent output for context injection."""
    text = json.dumps(output, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(truncated)"
