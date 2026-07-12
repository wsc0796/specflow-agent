"""Coordinator — top-level orchestrator for multi-agent workflows.

Wires together the planner, compiler, validator, enricher, and revision
controller to produce an :class:`EffectiveDelegationPlan` ready for
execution by the :class:`MultiAgentScheduler`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from specflow.agents.models import AgentConstraints
from specflow.agents.registry import AgentRegistry
from specflow.coordinator.revision import RevisionController
from specflow.coordinator.state_machine import MultiAgentWorkflowEngine
from specflow.plan.compiler import PlanCompiler
from specflow.plan.enricher import SemanticPlanEnricher
from specflow.plan.hash_utils import (
    compute_effective_plan_hash,
    compute_semantic_brief_hash,
)
from specflow.plan.models import AgentTask, EffectiveDelegationPlan
from specflow.plan.planner import DeterministicPlanner
from specflow.plan.validator import PlanValidator


class Coordinator:
    """Top-level orchestrator for multi-agent workflows.

    Parameters
    ----------
    agent_registry:
        Registry of available agent instances (used during execution,
        not directly during planning).
    llm_client:
        An object implementing the ``LLMClient`` protocol (``.complete`` method),
        passed through to the :class:`SemanticPlanEnricher`.
    model:
        Model identifier sent in every LLM enrichment request.
    provider:
        Provider name stored in enrichment provenance records.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry | None = None,
        llm_client: Any = None,
        model: str = "unknown",
        provider: str = "unknown",
        schema_registry: Any = None,
    ) -> None:
        self._registry = agent_registry
        self._llm_client = llm_client
        self._model = model
        self._provider = provider
        self._schema_registry = schema_registry
        self._engine = MultiAgentWorkflowEngine()
        self._revision_controller: RevisionController | None = None

    # ── Public properties ───────────────────────────────────────────

    @property
    def engine(self) -> MultiAgentWorkflowEngine:
        """The workflow state machine engine."""
        return self._engine

    @property
    def revision_controller(self) -> RevisionController | None:
        """The revision controller created during the last :meth:`plan` call."""
        return self._revision_controller

    # ── Planning ────────────────────────────────────────────────────

    def plan(self, run_id: str) -> EffectiveDelegationPlan:
        """Build an executable delegation plan for the fixed 6-agent topology.

        Steps
        -----
        1. Generate a :class:`StructuralDelegationSpec` (via :class:`DeterministicPlanner`).
        2. Compile it into a :class:`CompiledStructuralPlan` (via :class:`PlanCompiler`).
        3. Validate the compiled plan structurally (via :class:`PlanValidator`).
        4. Enrich each agent's task with a semantic brief (via :class:`SemanticPlanEnricher`).
        5. Compute the ``semantic_brief_hash`` from the enriched briefs.
        6. Build the :class:`AgentTask` list, binding identity, stage,
           dependencies, constraints, and brief.
        7. Create a :class:`RevisionController` from the plan's revision policy.
        8. Compute the ``effective_plan_hash`` and return an :class:`EffectiveDelegationPlan`.
        """
        # Step 1-2: Structural plan generation and compilation
        planner = DeterministicPlanner()
        spec = planner.generate()

        compiler = PlanCompiler()
        compiled = compiler.compile(spec)

        # Step 3: Structural validation (with schema registry when available)
        validator = PlanValidator()
        validator.validate(compiled, schema_registry=self._schema_registry)

        # Step 4: Semantic enrichment
        enricher = SemanticPlanEnricher(
            llm_client=self._llm_client,
            model=self._model,
            provider=self._provider,
        )
        briefs = enricher.enrich(spec)

        # Step 5: Compute semantic brief hash
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

        # Step 6: Build AgentTask list
        stage_map: dict[str, int] = {}
        for idx, stage in enumerate(compiled.execution_stages):
            for agent_id in stage:
                stage_map[agent_id] = idx

        dep_map: dict[str, frozenset[str]] = {
            d.agent_id: d.depends_on for d in compiled.dependencies
        }

        constraints_map: dict[str, AgentConstraints] = {c.agent_id: c for c in compiled.constraints}

        tasks = tuple(
            AgentTask(
                agent_id=a.agent_id,
                role=a.role,
                stage=stage_map[a.agent_id],
                depends_on=dep_map.get(a.agent_id, frozenset()),
                constraints=constraints_map[a.agent_id],
                task_brief=briefs[i],
            )
            for i, a in enumerate(compiled.agents)
        )

        # Step 7: Create RevisionController
        self._revision_controller = RevisionController(compiled.revision_policy)

        # Step 8: Compute effective plan hash and return final plan
        effective_plan_hash = compute_effective_plan_hash(
            compiled.structure_hash, semantic_brief_hash
        )

        return EffectiveDelegationPlan(
            plan_id=compiled.plan_id,
            run_id=run_id,
            structure_hash=compiled.structure_hash,
            semantic_brief_hash=semantic_brief_hash,
            effective_plan_hash=effective_plan_hash,
            stages=compiled.execution_stages,
            tasks=tasks,
            revision_policy=compiled.revision_policy,
            generated_at=datetime.now(UTC).isoformat(),
        )
