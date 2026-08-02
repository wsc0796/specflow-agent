from __future__ import annotations

from typing import Any

from specflow.agents.models import AgentRole
from specflow.plan.models import (
    ControlledEvidenceSummary,
    EnrichmentProvenance,
    EnrichmentStatus,
    EvidenceReference,
    SemanticTaskBrief,
)
from specflow.schema.models import AgentExecutionInput

TEST_HASH = "a" * 64


def controlled_evidence(
    *,
    content: str = "Verified evidence: src/app.py:1",
    references: tuple[EvidenceReference, ...] = (),
) -> ControlledEvidenceSummary:
    return ControlledEvidenceSummary(
        content=content,
        evidence_hash=TEST_HASH,
        references=references,
    )


def evidence_reference(evidence_id: str = "evidence-app") -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        relative_path="src/app.py",
        line_number=1,
        source_hash="b" * 64,
    )


def provenance(
    status: EnrichmentStatus = EnrichmentStatus.ENRICHED,
) -> EnrichmentProvenance:
    return EnrichmentProvenance(
        provider="test-provider",
        model="test-model",
        prompt_id="enrichment/test/v1",
        prompt_version="1.0.0",
        trace_id=f"trace-{status.value}",
        generated_at="2026-08-02T00:00:00+00:00",
        requirement_hash="c" * 64,
        evidence_summary_hash="d" * 64,
        outcome=status,
        failure_type="provider_error" if status is EnrichmentStatus.DEGRADED else None,
    )


def task_brief(
    *,
    agent_id: str = "test-agent-v1",
    role: AgentRole = AgentRole.DESIGN,
    output_schema_id: str = "agent/test/v1/output",
    task_description: str = "Inspect the design boundary",
    evidence_refs: tuple[EvidenceReference, ...] = (),
    status: EnrichmentStatus = EnrichmentStatus.ENRICHED,
    **overrides: Any,
) -> SemanticTaskBrief:
    values: dict[str, Any] = {
        "agent_id": agent_id,
        "role": role,
        "output_schema_id": output_schema_id,
        "task_description": task_description,
        "analysis_focus": ("interfaces",),
        "evaluation_hints": ("cite evidence",),
        "repository_scope_hint": "src/",
        "evidence_refs": evidence_refs,
        "status": status,
        "provenance": provenance(status),
    }
    values.update(overrides)
    return SemanticTaskBrief.model_validate(values)


def execution_input(
    *,
    brief: SemanticTaskBrief | None = None,
    evidence: ControlledEvidenceSummary | None = None,
    requirement: str = "Add a search API",
    prior_outputs: dict[str, dict[str, Any]] | None = None,
) -> AgentExecutionInput:
    selected_brief = brief or task_brief()
    return AgentExecutionInput(
        run_id="run-test",
        stage=1,
        agent_id=selected_brief.agent_id,
        role=selected_brief.role,
        requirement=requirement,
        evidence_summary=evidence or controlled_evidence(),
        repository_analysis={"summary": "validated repository analysis"},
        task_brief=selected_brief,
        prior_outputs=prior_outputs or {},
        revision_context=None,
        output_schema_id=selected_brief.output_schema_id,
    )
