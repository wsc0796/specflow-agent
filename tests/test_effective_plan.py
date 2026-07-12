"""Tests for AgentTask and EffectiveDelegationPlan models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from specflow.agents.models import (
    AgentConstraints,
    AgentRole,
    RevisionPolicy,
)
from specflow.plan.models import (
    AgentTask,
    EffectiveDelegationPlan,
    EnrichmentProvenance,
    EnrichmentStatus,
    SemanticTaskBrief,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_constraints(agent_id: str, **overrides: Any) -> AgentConstraints:
    defaults: dict[str, Any] = dict(
        agent_id=agent_id,
        max_execution_seconds=120,
        max_token_budget=8192,
        max_revision_rounds=1,
        allowed_paths=(),
        denied_paths=(),
    )
    defaults.update(overrides)
    return AgentConstraints(**defaults)


def _enriched_brief(agent_id: str, **overrides: Any) -> SemanticTaskBrief:
    """Create a fully enriched task brief."""
    defaults: dict[str, Any] = dict(
        agent_id=agent_id,
        task_description=f"Enriched task for {agent_id}",
        analysis_focus=(),
        evaluation_hints=(),
        repository_scope_hint="",
        enrichment_status=EnrichmentStatus.ENRICHED,
        provenance=EnrichmentProvenance(
            provider="test-provider",
            model="test-model",
            prompt_id="enrichment/test/v1",
            prompt_version="1.0.0",
            trace_id=f"trace-{agent_id}",
            generated_at=datetime.now(UTC).isoformat(),
        ),
    )
    defaults.update(overrides)
    return SemanticTaskBrief(**defaults)


def _degraded_brief(agent_id: str, **overrides: Any) -> SemanticTaskBrief:
    """Create a degraded (fallback) task brief."""
    defaults: dict[str, Any] = dict(
        agent_id=agent_id,
        task_description=f"Degraded task for {agent_id}",
    )
    defaults.update(overrides)
    return SemanticTaskBrief.degraded_default(**defaults)


# ------------------------------------------------------------------
# AgentTask
# ------------------------------------------------------------------


class TestAgentTask:
    def test_enriched_property_true(self) -> None:
        brief = _enriched_brief("a1")
        task = AgentTask(
            agent_id="a1",
            role=AgentRole.DESIGN,
            stage=0,
            depends_on=frozenset(),
            constraints=_make_constraints("a1"),
            task_brief=brief,
        )
        assert task.enriched is True

    def test_enriched_property_false(self) -> None:
        brief = _degraded_brief("a1")
        task = AgentTask(
            agent_id="a1",
            role=AgentRole.DESIGN,
            stage=0,
            depends_on=frozenset(),
            constraints=_make_constraints("a1"),
            task_brief=brief,
        )
        assert task.enriched is False

    def test_frozen_dataclass(self) -> None:
        brief = _enriched_brief("a1")
        task = AgentTask(
            agent_id="a1",
            role=AgentRole.REPOSITORY_ANALYST,
            stage=0,
            depends_on=frozenset(),
            constraints=_make_constraints("a1"),
            task_brief=brief,
        )
        with pytest.raises(AttributeError):
            task.agent_id = "new-id"  # type: ignore[misc]


# ------------------------------------------------------------------
# EffectiveDelegationPlan
# ------------------------------------------------------------------


def _build_effective_plan(
    all_enriched: bool,
    plan_id: str = "test-plan",
    run_id: str = "test-run",
) -> EffectiveDelegationPlan:
    """Helper: build an EffectiveDelegationPlan with 2 agents.

    When *all_enriched* is True both task briefs are enriched;
    otherwise both are degraded.
    """
    factory = _enriched_brief if all_enriched else _degraded_brief
    a1_brief = factory("a1", task_description="Repo analysis")
    a2_brief = factory("a2", task_description="Design work")
    tasks = (
        AgentTask(
            agent_id="a1",
            role=AgentRole.REPOSITORY_ANALYST,
            stage=0,
            depends_on=frozenset(),
            constraints=_make_constraints("a1"),
            task_brief=a1_brief,
        ),
        AgentTask(
            agent_id="a2",
            role=AgentRole.DESIGN,
            stage=1,
            depends_on=frozenset({"a1"}),
            constraints=_make_constraints("a2"),
            task_brief=a2_brief,
        ),
    )
    stages: tuple[tuple[str, ...], ...] = (("a1",), ("a2",))
    return EffectiveDelegationPlan(
        plan_id=plan_id,
        run_id=run_id,
        structure_hash="s1",
        semantic_brief_hash="s2",
        effective_plan_hash="s3",
        stages=stages,
        tasks=tasks,
        revision_policy=RevisionPolicy(),
        generated_at=datetime.now(UTC).isoformat(),
    )


class TestEffectiveDelegationPlan:
    def test_build_from_spec_compiled_briefs(self) -> None:
        """Build EffectiveDelegationPlan from a real spec, compiled plan, and enriched briefs,
        matching the standard 6-agent topology with 4 execution stages."""
        from specflow.plan.compiler import PlanCompiler
        from specflow.plan.hash_utils import (
            compute_effective_plan_hash,
            compute_semantic_brief_hash,
        )
        from specflow.plan.planner import DeterministicPlanner

        planner = DeterministicPlanner()
        spec = planner.generate("integration-test-plan")
        compiler = PlanCompiler()
        compiled = compiler.compile(spec)

        # Enriched briefs for all 6 agents
        briefs = tuple(
            _enriched_brief(
                a.agent_id,
                task_description=f"Execute {a.role.value} analysis",
                analysis_focus=(f"{a.role.value}_focus",),
            )
            for a in spec.agents
        )

        # Map agent_id -> stage index
        stage_map: dict[str, int] = {}
        for idx, stage in enumerate(compiled.execution_stages):
            for agent_id in stage:
                stage_map[agent_id] = idx

        # Map agent_id -> depends_on frozenset
        dep_map: dict[str, frozenset[str]] = {d.agent_id: d.depends_on for d in spec.dependencies}

        # Map agent_id -> constraints
        constraints_map: dict[str, AgentConstraints] = {c.agent_id: c for c in spec.constraints}

        tasks = tuple(
            AgentTask(
                agent_id=a.agent_id,
                role=a.role,
                stage=stage_map[a.agent_id],
                depends_on=dep_map.get(a.agent_id, frozenset()),
                constraints=constraints_map[a.agent_id],
                task_brief=briefs[i],
            )
            for i, a in enumerate(spec.agents)
        )

        # Compute semantic brief hash
        brief_dicts = [
            {
                "agent_id": b.agent_id,
                "task_description": b.task_description,
                "analysis_focus": list(b.analysis_focus),
                "evaluation_hints": list(b.evaluation_hints),
                "repository_scope_hint": b.repository_scope_hint,
            }
            for b in briefs
        ]
        semantic_brief_hash = compute_semantic_brief_hash(brief_dicts)
        effective_plan_hash = compute_effective_plan_hash(
            compiled.structure_hash, semantic_brief_hash
        )

        plan = EffectiveDelegationPlan(
            plan_id=compiled.plan_id,
            run_id="integration-run",
            structure_hash=compiled.structure_hash,
            semantic_brief_hash=semantic_brief_hash,
            effective_plan_hash=effective_plan_hash,
            stages=compiled.execution_stages,
            tasks=tasks,
            revision_policy=spec.revision_policy,
            generated_at=datetime.now(UTC).isoformat(),
        )

        # Verify 6 tasks
        assert plan.plan_id == "integration-test-plan"
        assert len(plan.tasks) == 6
        # Verify 4 execution stages
        assert len(plan.stages) == 4
        # Stage 0: repository-analyst alone
        assert len(plan.stages[0]) == 1
        # Stage 1: design, test-strategy, risk-review (parallel)
        assert len(plan.stages[1]) == 3
        # Stage 2: synthesis
        assert len(plan.stages[2]) == 1
        # Stage 3: review
        assert len(plan.stages[3]) == 1

        # All briefs enriched
        assert plan.enriched is True
        assert plan.degraded_agents == ()

    def test_all_enriched_derived_properties(self) -> None:
        """All enriched -> enriched=True, degraded_agents=()."""
        plan = _build_effective_plan(all_enriched=True)
        assert plan.enriched is True
        assert plan.degraded_agents == ()

    def test_all_degraded_derived_properties(self) -> None:
        """All degraded -> enriched=False, degraded_agents lists both agent IDs."""
        plan = _build_effective_plan(all_enriched=False)
        assert plan.enriched is False
        assert plan.degraded_agents == ("a1", "a2")

    def test_partial_enrichment(self) -> None:
        """Mixed enrichment -> correct degraded_agents listing."""
        tasks = (
            AgentTask(
                agent_id="enriched-agent",
                role=AgentRole.DESIGN,
                stage=0,
                depends_on=frozenset(),
                constraints=_make_constraints("enriched-agent"),
                task_brief=_enriched_brief("enriched-agent"),
            ),
            AgentTask(
                agent_id="degraded-agent",
                role=AgentRole.REVIEW,
                stage=1,
                depends_on=frozenset({"enriched-agent"}),
                constraints=_make_constraints("degraded-agent"),
                task_brief=_degraded_brief("degraded-agent"),
            ),
        )
        stages: tuple[tuple[str, ...], ...] = (
            ("enriched-agent",),
            ("degraded-agent",),
        )
        plan = EffectiveDelegationPlan(
            plan_id="partial-test",
            run_id="run-partial",
            structure_hash="h1",
            semantic_brief_hash="h2",
            effective_plan_hash="h3",
            stages=stages,
            tasks=tasks,
            revision_policy=RevisionPolicy(),
            generated_at=datetime.now(UTC).isoformat(),
        )
        assert plan.enriched is False
        assert plan.degraded_agents == ("degraded-agent",)

    def test_frozen_dataclass(self) -> None:
        """EffectiveDelegationPlan is truly frozen."""
        plan = _build_effective_plan(all_enriched=True)
        with pytest.raises(AttributeError):
            plan.plan_id = "new-id"  # type: ignore[misc]
