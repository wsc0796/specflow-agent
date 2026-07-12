"""Tests for Coordinator — top-level multi-agent workflow orchestrator."""

from __future__ import annotations

import json
from typing import Any

import pytest

from specflow.agents.models import AgentRole
from specflow.coordinator.coordinator import Coordinator
from specflow.coordinator.revision import RevisionController
from specflow.coordinator.state_machine import MultiAgentWorkflowEngine
from specflow.llm.mock import MockLLMClient
from specflow.plan.models import EffectiveDelegationPlan


def _mock_enrichment_response() -> str:
    """Generate a deterministic JSON response for the enrichment prompt."""
    return json.dumps(
        {
            "task_description": "Perform analysis on the repository",
            "analysis_focus": ["structure", "dependencies", "patterns"],
            "evaluation_hints": ["check consistency", "verify coverage"],
            "repository_scope_hint": "Focus on src/ directory",
        }
    )


class TestCoordinatorConstruction:
    """Verify Coordinator is properly constructed."""

    def test_minimal_construction(self) -> None:
        coordinator = Coordinator()
        assert coordinator._registry is None
        assert coordinator._llm_client is None
        assert coordinator._model == "unknown"
        assert coordinator._provider == "unknown"

    def test_custom_construction(self) -> None:
        llm = MockLLMClient(response_content=_mock_enrichment_response())
        coordinator = Coordinator(
            agent_registry=None,  # type: ignore[arg-type]
            llm_client=llm,
            model="gpt-4",
            provider="openai",
        )
        assert coordinator._model == "gpt-4"
        assert coordinator._provider == "openai"

    def test_engine_created_by_default(self) -> None:
        coordinator = Coordinator()
        assert isinstance(coordinator.engine, MultiAgentWorkflowEngine)

    def test_revision_controller_initial_none(self) -> None:
        coordinator = Coordinator()
        assert coordinator.revision_controller is None


class TestCoordinatorPlan:
    """Verify Coordinator.plan() produces a valid EffectiveDelegationPlan."""

    @pytest.fixture(autouse=True)
    def _setup_coordinator(self) -> None:
        """Create a coordinator backed by a mock LLM that responds with valid JSON."""
        llm = MockLLMClient(response_content=_mock_enrichment_response())
        self._coordinator = Coordinator(
            llm_client=llm,
            model="test-model",
            provider="test-provider",
        )

    # ── Basic structure ─────────────────────────────────────────────

    def test_plan_returns_effective_delegation_plan(self) -> None:
        """plan() returns an EffectiveDelegationPlan."""
        plan = self._coordinator.plan(run_id="test-run-001")
        assert isinstance(plan, EffectiveDelegationPlan)

    def test_plan_has_correct_run_id(self) -> None:
        plan = self._coordinator.plan(run_id="my-run")
        assert plan.run_id == "my-run"

    def test_plan_custom_run_id(self) -> None:
        plan = self._coordinator.plan(run_id="another-run")
        assert plan.run_id == "another-run"

    # ── Hash verification ───────────────────────────────────────────

    def test_plan_has_all_three_hashes(self) -> None:
        """EffectiveDelegationPlan contains all three hashes and they are non-empty."""
        plan = self._coordinator.plan(run_id="hash-test")

        assert isinstance(plan.structure_hash, str)
        assert len(plan.structure_hash) == 64  # SHA-256 hex

        assert isinstance(plan.semantic_brief_hash, str)
        assert len(plan.semantic_brief_hash) == 64  # SHA-256 hex

        assert isinstance(plan.effective_plan_hash, str)
        assert len(plan.effective_plan_hash) == 64  # SHA-256 hex

    def test_hashes_are_different(self) -> None:
        """All three hashes should be distinct from each other."""
        plan = self._coordinator.plan(run_id="hash-unique")

        assert plan.structure_hash != plan.semantic_brief_hash
        assert plan.structure_hash != plan.effective_plan_hash
        assert plan.semantic_brief_hash != plan.effective_plan_hash

    def test_deterministic_hashes_for_same_plan(self) -> None:
        """Two calls with the same inputs produce the same hashes."""
        plan1 = self._coordinator.plan(run_id="test-deterministic")
        plan2 = self._coordinator.plan(run_id="test-deterministic")  # noqa: Duplicate call

        # Note: briefs are enriched fresh each call but the mock returns the same
        # JSON, so hashes should be identical.
        assert plan1.structure_hash == plan2.structure_hash
        assert plan1.semantic_brief_hash == plan2.semantic_brief_hash
        assert plan1.effective_plan_hash == plan2.effective_plan_hash

    # ── Task count and roles ────────────────────────────────────────

    def test_plan_has_six_tasks(self) -> None:
        """The fixed 6-agent topology produces 6 AgentTasks."""
        plan = self._coordinator.plan(run_id="six-tasks")
        assert len(plan.tasks) == 6

    def test_all_six_roles_present(self) -> None:
        """All six AgentRole values appear across the tasks."""
        plan = self._coordinator.plan(run_id="all-roles")
        roles = {t.role for t in plan.tasks}
        expected_roles = {
            AgentRole.REPOSITORY_ANALYST,
            AgentRole.DESIGN,
            AgentRole.TEST_STRATEGY,
            AgentRole.RISK_REVIEW,
            AgentRole.SYNTHESIS,
            AgentRole.REVIEW,
        }
        assert roles == expected_roles

    def test_all_agent_ids_match_fixed_topology(self) -> None:
        """Task agent_ids match the known fixed-topology agent IDs."""
        plan = self._coordinator.plan(run_id="agent-ids")
        agent_ids = {t.agent_id for t in plan.tasks}
        expected = {
            "repository-analyst-agent-v1",
            "design-agent-v1",
            "test-strategy-agent-v1",
            "risk-review-agent-v1",
            "synthesis-agent-v1",
            "review-agent-v1",
        }
        assert agent_ids == expected

    # ── Stage assignment ────────────────────────────────────────────

    def test_plan_has_four_stages(self) -> None:
        """The compiled plan has 4 execution stages."""
        plan = self._coordinator.plan(run_id="stages")
        assert len(plan.stages) == 4

    def test_correct_stage_assignments(self) -> None:
        """Agents are assigned to the correct stages.

        Stage 0: repository-analyst (alone)
        Stage 1: design, test-strategy, risk-review (parallel)
        Stage 2: synthesis (alone)
        Stage 3: review (alone)
        """
        plan = self._coordinator.plan(run_id="stage-assign")

        stage_map: dict[str, int] = {}
        for idx, stage in enumerate(plan.stages):
            for agent_id in stage:
                stage_map[agent_id] = idx

        # Stage 0
        assert stage_map["repository-analyst-agent-v1"] == 0
        assert len(plan.stages[0]) == 1

        # Stage 1
        assert stage_map["design-agent-v1"] == 1
        assert stage_map["test-strategy-agent-v1"] == 1
        assert stage_map["risk-review-agent-v1"] == 1
        assert len(plan.stages[1]) == 3

        # Stage 2
        assert stage_map["synthesis-agent-v1"] == 2
        assert len(plan.stages[2]) == 1

        # Stage 3
        assert stage_map["review-agent-v1"] == 3
        assert len(plan.stages[3]) == 1

    def test_task_stage_index_matches_stages(self) -> None:
        """Each task's .stage field matches its position in plan.stages."""
        plan = self._coordinator.plan(run_id="task-stage-match")

        stage_map: dict[str, int] = {}
        for idx, stage in enumerate(plan.stages):
            for agent_id in stage:
                stage_map[agent_id] = idx

        for task in plan.tasks:
            assert task.stage == stage_map[task.agent_id], (
                f"Task {task.agent_id} has stage={task.stage} "
                f"but plan.stages puts it at stage={stage_map[task.agent_id]}"
            )

    # ── Dependency information ──────────────────────────────────────

    def test_correct_dependencies(self) -> None:
        """Verify task dependencies match the expected topology."""
        plan = self._coordinator.plan(run_id="deps")
        dep_map: dict[str, frozenset[str]] = {t.agent_id: t.depends_on for t in plan.tasks}

        assert dep_map["repository-analyst-agent-v1"] == frozenset()
        assert dep_map["design-agent-v1"] == frozenset({"repository-analyst-agent-v1"})
        assert dep_map["test-strategy-agent-v1"] == frozenset({"repository-analyst-agent-v1"})
        assert dep_map["risk-review-agent-v1"] == frozenset({"repository-analyst-agent-v1"})
        assert dep_map["synthesis-agent-v1"] == frozenset(
            {"design-agent-v1", "test-strategy-agent-v1", "risk-review-agent-v1"}
        )
        assert dep_map["review-agent-v1"] == frozenset({"synthesis-agent-v1"})

    # ── Revision controller ─────────────────────────────────────────

    def test_revision_controller_created_after_plan(self) -> None:
        """Calling plan() creates a RevisionController accessible via property."""
        assert self._coordinator.revision_controller is None
        self._coordinator.plan(run_id="rev-test")
        assert isinstance(self._coordinator.revision_controller, RevisionController)

    def test_revision_controller_has_default_policy(self) -> None:
        """The RevisionController uses the default RevisionPolicy (max_total_rounds=1)."""
        self._coordinator.plan(run_id="rev-policy")
        rc = self._coordinator.revision_controller
        assert rc is not None
        assert rc.policy.max_total_rounds == 1
        assert rc.exhausted is False

    # ── Enriched tasks ──────────────────────────────────────────────

    def test_all_tasks_are_enriched(self) -> None:
        """With a working mock LLM, all task briefs should be ENRICHED."""
        plan = self._coordinator.plan(run_id="enriched")
        assert plan.enriched is True
        assert plan.degraded_agents == ()

    def test_task_briefs_have_content(self) -> None:
        """Each task brief should have non-empty content from the mock LLM."""
        plan = self._coordinator.plan(run_id="brief-content")
        for task in plan.tasks:
            brief = task.task_brief
            assert brief.enrichment_status.name == "ENRICHED"
            assert len(brief.task_description) > 0
            assert len(brief.analysis_focus) > 0

    # ── Frozen dataclass ────────────────────────────────────────────

    def test_plan_is_frozen(self) -> None:
        plan = self._coordinator.plan(run_id="frozen")
        with pytest.raises(AttributeError):
            plan.plan_id = "new-id"  # type: ignore[misc]

    # ── Metadata ────────────────────────────────────────────────────

    def test_plan_id_default(self) -> None:
        """Plan ID should default to 'plan-v1' from DeterministicPlanner."""
        plan = self._coordinator.plan(run_id="meta")
        assert plan.plan_id == "plan-v1"

    def test_generated_at_is_set(self) -> None:
        """Plan should have a non-empty generated_at timestamp."""
        plan = self._coordinator.plan(run_id="meta-ts")
        assert isinstance(plan.generated_at, str)
        assert len(plan.generated_at) > 0
        assert "T" in plan.generated_at
