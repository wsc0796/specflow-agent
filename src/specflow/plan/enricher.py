"""Semantic plan enricher — enriches a structural plan with per-agent task briefs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from specflow.llm.models import LLMMessage, LLMRequest
from specflow.plan.models import (
    EnrichmentProvenance,
    EnrichmentStatus,
    SemanticTaskBrief,
    StructuralDelegationSpec,
)


class SemanticPlanEnricher:
    """Produces semantic task briefs for every agent in a structural plan.

    For each agent an LLM call is made to generate a structured brief
    describing what the agent should focus on.  If any single call fails
    a degraded (non-enriched) brief is used for that agent while the
    rest of the enrichment proceeds normally.
    """

    def __init__(self, llm_client: Any, model: str, provider: str) -> None:
        """Store references.  Does **not** call the LLM.

        Parameters
        ----------
        llm_client:
            An object implementing the ``LLMClient`` protocol (i.e. a
            ``.complete(request: LLMRequest) -> LLMResponse`` method).
        model:
            Model identifier passed through to each ``LLMRequest``.
        provider:
            Provider name stored in every ``EnrichmentProvenance`` entry.
        """
        self._llm = llm_client
        self._model = model
        self._provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich(
        self, spec: StructuralDelegationSpec
    ) -> tuple[SemanticTaskBrief, ...]:
        """Enrich *spec* with one brief per agent.

        A failed enrichment for an individual agent results in a degraded
        (fallback) brief for that agent only — other agents are unaffected.
        """
        briefs: list[SemanticTaskBrief] = []
        for agent in spec.agents:
            try:
                brief = self._enrich_one(agent.agent_id, agent.role.value)
            except Exception:
                brief = SemanticTaskBrief.degraded_default(
                    agent_id=agent.agent_id,
                    task_description=(
                        f"Execute {agent.role.value} analysis "
                        f"for the given requirement."
                    ),
                )
            briefs.append(brief)
        return tuple(briefs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enrich_one(self, agent_id: str, role: str) -> SemanticTaskBrief:
        """Enrich a single agent, raising on any failure."""
        prompt_text = self._build_enrichment_prompt(agent_id, role)
        request = LLMRequest(
            model=self._model,
            messages=[LLMMessage(role="user", content=prompt_text)],
            temperature=0.0,
            max_tokens=1024,
            response_format="json",
        )
        response = self._llm.complete(request)
        data = json.loads(response.content)
        now = datetime.now(timezone.utc).isoformat()

        return SemanticTaskBrief(
            agent_id=agent_id,
            task_description=data.get("task_description", ""),
            analysis_focus=tuple(data.get("analysis_focus", [])),
            evaluation_hints=tuple(data.get("evaluation_hints", [])),
            repository_scope_hint=data.get("repository_scope_hint", ""),
            enrichment_status=EnrichmentStatus.ENRICHED,
            provenance=EnrichmentProvenance(
                provider=self._provider,
                model=self._model,
                prompt_id=f"enrichment/{role}/v1",
                prompt_version="1.0.0",
                trace_id="",
                generated_at=now,
            ),
        )

    @staticmethod
    def _build_enrichment_prompt(agent_id: str, role: str) -> str:
        return (
            f'Generate a task brief for agent "{agent_id}" with role "{role}". '
            f'Return JSON: {{"task_description": "...", "analysis_focus": [...], '
            f'"evaluation_hints": [...], "repository_scope_hint": "..."}}'
        )
