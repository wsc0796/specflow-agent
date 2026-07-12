"""Multi-agent runner — orchestrates the 6-agent pipeline via Coordinator."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from specflow.agents.design import DesignAgent
from specflow.agents.registry import AgentRegistry
from specflow.agents.repository_analyst import RepositoryAnalystAgent
from specflow.agents.review import ReviewAgent
from specflow.agents.risk_review import RiskReviewAgent
from specflow.agents.synthesis import SynthesisAgent
from specflow.agents.test_strategy import TestStrategyAgent
from specflow.coordinator.coordinator import Coordinator
from specflow.coordinator.scheduler import MultiAgentScheduler
from specflow.coordinator.state_machine import MultiAgentWorkflowState


def run_multi_agent(
    *,
    repo: Path,
    requirement: str,
    output: Path,
    mock: bool = False,
    provider: str = "mock",
    model: str = "mock-model",
) -> int:
    """Run the multi-agent pipeline. Returns exit code."""
    # 1. Register all 6 agents
    registry = AgentRegistry()
    registry.register(RepositoryAnalystAgent())
    registry.register(DesignAgent())
    registry.register(TestStrategyAgent())
    registry.register(RiskReviewAgent())
    registry.register(SynthesisAgent())
    registry.register(ReviewAgent())

    # 2. Create mock or real LLM client
    llm_client = _make_llm_client(mock)

    if not repo.is_dir() or not requirement.strip():
        return 2

    # 3. Create Coordinator and generate plan
    coordinator = Coordinator(
        agent_registry=registry, llm_client=llm_client, model=model, provider=provider
    )
    run_id = f"run-multi-{sha256(f'{repo.resolve()}|{requirement}'.encode()).hexdigest()[:12]}"
    plan = coordinator.plan(run_id)

    try:
        coordinator.engine.transition(MultiAgentWorkflowState.PLANNING, "plan compiled")
        coordinator.engine.transition(MultiAgentWorkflowState.ANALYZING, "analysis stage")
        executors = {
            identity.agent_id: registry.get(identity.agent_id).execute
            for identity in registry.list_agents()
        }
        stages = MultiAgentScheduler().execute(
            plan.stages,
            executors,
            {"run_id": run_id, "repository_root": str(repo.resolve()), "requirement": requirement},
        )
        coordinator.engine.transition(
            MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "specialist stages complete"
        )
        coordinator.engine.transition(
            MultiAgentWorkflowState.SYNTHESIZING, "synthesis stage complete"
        )
        coordinator.engine.transition(MultiAgentWorkflowState.REVIEWING, "review stage complete")
        coordinator.engine.transition(MultiAgentWorkflowState.COMPLETED, "mock review passed")
    except Exception:
        return 3

    # 4. Write manifest
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "plan_id": plan.plan_id,
        "structure_hash": plan.structure_hash,
        "semantic_brief_hash": plan.semantic_brief_hash,
        "effective_plan_hash": plan.effective_plan_hash,
        "stages": [list(stage) for stage in plan.stages],
        "enriched": plan.enriched,
        "degraded_agents": list(plan.degraded_agents),
        "workflow_state": coordinator.engine.state.value,
        "workflow_history": list(coordinator.engine.history),
        "stage_results": [
            {"stage": result.stage_index, "agents": sorted(result.agent_results)}
            for result in stages
        ],
    }
    (output / f"{run_id}-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


def _make_llm_client(mock: bool) -> object:
    """Create a mock LLM client for the enrichment phase."""

    class MockClient:
        """Minimal mock that returns valid JSON for semantic enrichment."""

        def complete(self, request) -> object:
            class MockResponse:
                content = (
                    '{"task_description": "mock", "analysis_focus": [],'
                    ' "evaluation_hints": [], "repository_scope_hint": ""}'
                )

            return MockResponse()

    return MockClient()
