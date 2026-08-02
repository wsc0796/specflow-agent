"""Tests for SemanticPlanEnricher."""

from __future__ import annotations

import json
from typing import Any

import pytest
from task_brief_test_helpers import controlled_evidence, evidence_reference, provenance

from specflow.agents.models import (
    AgentConstraints,
    AgentDependency,
    AgentIdentity,
    AgentRole,
    RevisionPolicy,
)
from specflow.llm.exceptions import LLMResponseError
from specflow.llm.models import LLMRequest, LLMResponse, LLMUsage
from specflow.plan.enricher import SemanticPlanEnricher
from specflow.plan.models import (
    EnrichmentProvenance,
    EnrichmentStatus,
    SemanticTaskBrief,
    StructuralDelegationSpec,
)

# ====================================================================
# Test doubles (Fake / Failing LLM clients)
# ====================================================================


class FakeLLMClient:
    """Returns a canned JSON response for any request."""

    def __init__(self, response_json: dict[str, Any]) -> None:
        self._response_json = response_json
        self.last_request: LLMRequest | None = None

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        content = json.dumps(self._response_json, ensure_ascii=False)
        return LLMResponse(
            content=content,
            model=request.model,
            usage=LLMUsage(input_tokens=10, output_tokens=20),
            latency_ms=5,
            finish_reason="stop",
        )


class FailingLLMClient:
    """Always raises on ``complete``."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise LLMResponseError("Simulated LLM failure")


# ====================================================================
# Fixtures
# ====================================================================


def _make_spec(agent_count: int = 2) -> StructuralDelegationSpec:
    """Create a minimal StructuralDelegationSpec for testing."""
    agents: list[AgentIdentity] = [
        AgentIdentity(
            agent_id=f"agent-{i}",
            role=list(AgentRole)[i % len(list(AgentRole))],
            version="1.0.0",
            description=f"Agent {i}",
            prompt_id="test/v1",
            prompt_version="1.0.0",
            input_schema_id="test/v1/input",
            output_schema_id="test/v1/output",
        )
        for i in range(agent_count)
    ]
    deps = tuple(AgentDependency(agent_id=a.agent_id, depends_on=frozenset()) for a in agents)
    constraints = tuple(
        AgentConstraints(
            agent_id=a.agent_id,
            max_execution_seconds=60,
            max_token_budget=4096,
        )
        for a in agents
    )
    return StructuralDelegationSpec(
        plan_id="test-plan",
        agents=tuple(agents),
        dependencies=deps,
        constraints=constraints,
        revision_policy=RevisionPolicy(),
    )


def _enrich(
    enricher: SemanticPlanEnricher,
    spec: StructuralDelegationSpec,
) -> tuple[SemanticTaskBrief, ...]:
    return enricher.enrich(
        spec,
        requirement="Inspect the repository",
        evidence_summary=controlled_evidence(),
        output_schemas={agent.agent_id: {"type": "object"} for agent in spec.agents},
    )


# ====================================================================
# Tests
# ====================================================================


class TestEnrichAll:
    def test_enriches_all_agents(self) -> None:
        spec = _make_spec(3)
        llm = FakeLLMClient(
            {
                "task_description": "Analyze the codebase",
                "analysis_focus": ["structure", "patterns"],
                "evaluation_hints": ["check coverage"],
                "repository_scope_hint": "src/",
            }
        )
        enricher = SemanticPlanEnricher(llm_client=llm, model="gpt-4", provider="openai")
        briefs = _enrich(enricher, spec)

        assert len(briefs) == 3
        for brief in briefs:
            assert brief.enrichment_status == EnrichmentStatus.ENRICHED
            assert brief.provenance is not None
            assert brief.provenance.model == "gpt-4"
            assert brief.provenance.provider == "openai"

    def test_enriched_status_propagates(self) -> None:
        spec = _make_spec(1)
        llm = FakeLLMClient(
            {
                "task_description": "Test task",
                "analysis_focus": [],
                "evaluation_hints": [],
                "repository_scope_hint": "",
            }
        )
        enricher = SemanticPlanEnricher(llm_client=llm, model="gpt-4", provider="openai")
        briefs = _enrich(enricher, spec)

        assert briefs[0].enrichment_status == EnrichmentStatus.ENRICHED
        assert isinstance(briefs[0].provenance, EnrichmentProvenance)


class TestDegradedOnFailure:
    def test_llm_failure_produces_degraded(self) -> None:
        spec = _make_spec(2)
        llm = FailingLLMClient()
        enricher = SemanticPlanEnricher(llm_client=llm, model="gpt-4", provider="openai")
        briefs = _enrich(enricher, spec)

        assert len(briefs) == 2
        for brief in briefs:
            assert brief.enrichment_status == EnrichmentStatus.DEGRADED
            assert brief.provenance.failure_type == "provider_error"
            assert brief.task_description

    def test_malformed_json_produces_degraded(self) -> None:
        class MalformedLLMClient:
            def complete(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(
                    content="not valid json",
                    model="gpt-4",
                    usage=LLMUsage(input_tokens=10, output_tokens=5),
                    latency_ms=5,
                    finish_reason="stop",
                )

        spec = _make_spec(1)
        enricher = SemanticPlanEnricher(
            llm_client=MalformedLLMClient(), model="gpt-4", provider="openai"
        )
        briefs = _enrich(enricher, spec)

        assert len(briefs) == 1
        assert briefs[0].enrichment_status == EnrichmentStatus.DEGRADED
        assert briefs[0].provenance.failure_type == "invalid_json"

    def test_unknown_model_evidence_reference_produces_schema_degraded_brief(self) -> None:
        spec = _make_spec(1)
        llm = FakeLLMClient(
            {
                "task_description": "Cite invented evidence",
                "analysis_focus": [],
                "evaluation_hints": [],
                "repository_scope_hint": "",
                "evidence_refs": ["evidence-invented"],
            }
        )
        enricher = SemanticPlanEnricher(llm_client=llm, model="gpt-4", provider="openai")
        briefs = enricher.enrich(
            spec,
            requirement="Inspect the repository",
            evidence_summary=controlled_evidence(
                references=(evidence_reference("evidence-known"),)
            ),
            output_schemas={spec.agents[0].agent_id: {"type": "object"}},
        )
        assert briefs[0].status is EnrichmentStatus.DEGRADED
        assert briefs[0].evidence_refs == ()
        assert briefs[0].provenance.failure_type == "schema_validation_error"


class TestAgentSetPreservation:
    def test_enrichment_does_not_modify_agent_set(self) -> None:
        spec = _make_spec(4)
        original_ids = {a.agent_id for a in spec.agents}

        llm = FakeLLMClient(
            {
                "task_description": "task",
                "analysis_focus": [],
                "evaluation_hints": [],
                "repository_scope_hint": "",
            }
        )
        enricher = SemanticPlanEnricher(llm_client=llm, model="gpt-4", provider="openai")
        briefs = _enrich(enricher, spec)

        brief_ids = {b.agent_id for b in briefs}
        assert brief_ids == original_ids

    def test_mixed_failures_preserve_count(self) -> None:
        """One agent fails but total count stays the same."""

        class PartiallyFailingClient:
            def __init__(self) -> None:
                self._call_count = 0

            def complete(self, request: LLMRequest) -> LLMResponse:
                self._call_count += 1
                if self._call_count == 2:  # Second call fails
                    raise LLMResponseError("Partial failure")
                content = json.dumps(
                    {
                        "task_description": f"Task {self._call_count}",
                        "analysis_focus": [],
                        "evaluation_hints": [],
                        "repository_scope_hint": "",
                    }
                )
                return LLMResponse(
                    content=content,
                    model="gpt-4",
                    usage=LLMUsage(input_tokens=10, output_tokens=5),
                    latency_ms=5,
                    finish_reason="stop",
                )

        spec = _make_spec(3)
        enricher = SemanticPlanEnricher(
            llm_client=PartiallyFailingClient(), model="gpt-4", provider="openai"
        )
        briefs = _enrich(enricher, spec)

        assert len(briefs) == 3
        enriched = [b for b in briefs if b.enrichment_status == EnrichmentStatus.ENRICHED]
        degraded = [b for b in briefs if b.enrichment_status == EnrichmentStatus.DEGRADED]
        assert len(enriched) == 2
        assert len(degraded) == 1


class TestSemanticTaskBrief:
    def test_degraded_default_factory(self) -> None:
        brief = SemanticTaskBrief.degraded_default(
            agent_id="test-agent",
            role=AgentRole.DESIGN,
            output_schema_id="test/v1/output",
            task_description="do something",
            provenance=provenance(EnrichmentStatus.DEGRADED),
        )
        assert brief.agent_id == "test-agent"
        assert brief.enrichment_status == EnrichmentStatus.DEGRADED
        assert brief.provenance.failure_type == "provider_error"
        assert brief.analysis_focus == ()

    def test_empty_agent_id_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1 character"):
            SemanticTaskBrief(
                agent_id="",
                role=AgentRole.DESIGN,
                output_schema_id="test/v1/output",
                task_description="task",
                analysis_focus=(),
                evaluation_hints=(),
                repository_scope_hint="",
                enrichment_status=EnrichmentStatus.ENRICHED,
                provenance=provenance(),
            )

    def test_non_enum_status_raises(self) -> None:
        with pytest.raises(ValueError, match="enriched.*degraded"):
            SemanticTaskBrief(
                agent_id="a1",
                role=AgentRole.DESIGN,
                output_schema_id="test/v1/output",
                task_description="task",
                analysis_focus=(),
                evaluation_hints=(),
                repository_scope_hint="",
                enrichment_status="invalid",  # type: ignore[arg-type]
                provenance=provenance(),
            )
