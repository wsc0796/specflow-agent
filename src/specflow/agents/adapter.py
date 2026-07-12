"""Agent Runner — bridges Agent identity to LLM execution."""

from __future__ import annotations

import json
import time
from typing import Any

from specflow.agents.models import AgentIdentity
from specflow.llm.client import LLMClient
from specflow.llm.models import LLMMessage, LLMRequest
from specflow.policy.errors import ErrorCode, is_retryable as _is_retryable_error
from specflow.schema.registry import SchemaRegistry


class AgentRunner:
    """Wraps an Agent identity with LLM-backed execution.

    Does NOT modify the agent — it wraps the agent's identity and
    provides a callable ``execute(context)`` that goes through the
    real LLM provider.

    On failure, returns a safe, explicit failure envelope.  Unvalidated data
    is never made available to downstream agents.
    """

    def __init__(
        self,
        identity: AgentIdentity,
        llm_client: LLMClient,
        *,
        schema_registry: SchemaRegistry | None = None,
        system_prompt: str = "",
        model: str = "unknown",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        max_retries: int = 0,
    ) -> None:
        self._identity = identity
        self._llm = llm_client
        self._schema_registry = schema_registry
        self._system_prompt = system_prompt
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

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

        messages: list[LLMMessage] = []
        if self._system_prompt.strip():
            messages.append(LLMMessage(role="system", content=self._system_prompt))
        messages.append(LLMMessage(role="user", content=user_message))

        for attempt in range(self._max_retries + 1):
            try:
                response = self._llm.complete(
                    LLMRequest(
                        model=self._model,
                        messages=messages,
                        temperature=self._temperature,
                        max_tokens=self._max_tokens,
                        response_format="json",
                    )
                )
                break  # success
            except Exception as exc:
                error_code = _error_to_code(exc)
                retryable = _is_retryable_error(error_code)
                if not retryable or attempt >= self._max_retries:
                    return _failed_result(self._identity, error_code.value)
                backoff = min(0.5 * (2 ** attempt), 5.0)  # 0.5s, 1s, 2s, 4s, 5s cap
                time.sleep(backoff)

        try:
            data = json.loads(response.content)

            if self._schema_registry is None:
                return _failed_result(self._identity, "SCHEMA_REGISTRY_UNAVAILABLE")

            try:
                output_model = self._schema_registry.get(self._identity.output_schema_id)
                validated = output_model.model_validate(data)
                data = validated.model_dump()
            except Exception:
                return _failed_result(self._identity, "SCHEMA_VALIDATION_FAILED")

            return {
                "agent_id": self.agent_id,
                "role": self._identity.role.value,
                "success": True,
                "output": data,
                "model": self._model,
                "schema_validated": True,
                "usage": {
                    "input_tokens": getattr(response, "input_tokens", 0),
                    "output_tokens": getattr(response, "output_tokens", 0),
                },
            }
        except json.JSONDecodeError:
            return _failed_result(self._identity, "JSON_PARSE_FAILED")
        except Exception:
            return _failed_result(self._identity, "AGENT_EXECUTION_FAILED")


def _error_to_code(error: Exception) -> ErrorCode:
    """Classify a provider error; unknown failures are never retried."""
    err = str(error).lower()
    if "401" in err or "auth" in err or "unauthorized" in err:
        return ErrorCode.PROVIDER_AUTH_FAILURE
    if "429" in err or "rate" in err:
        return ErrorCode.PROVIDER_RATE_LIMITED
    if "timeout" in err or "timed out" in err:
        return ErrorCode.PROVIDER_TIMEOUT
    if "5" in err and ("server" in err or "500" in err or "502" in err or "503" in err):
        return ErrorCode.PROVIDER_SERVER_ERROR
    if "connection" in err or "network" in err:
        return ErrorCode.PROVIDER_CONNECTION_ERROR
    if "security" in err or "path" in err or "traversal" in err:
        return ErrorCode.SECURITY_PATH_TRAVERSAL
    return ErrorCode.INTERNAL_UNEXPECTED


def _failed_result(identity: AgentIdentity, error_code: str) -> dict[str, Any]:
    """Return an artifact-safe failure envelope without exception contents."""
    return {
        "agent_id": identity.agent_id,
        "role": identity.role.value,
        "success": False,
        "output": {"degraded": True, "error_code": error_code},
        "degraded": True,
        "schema_validated": False,
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
