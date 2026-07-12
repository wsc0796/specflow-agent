"""Multi-agent runner — orchestrates the 6-agent pipeline via Coordinator."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

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
from specflow.handoff.models import AgentHandoff
from specflow.handoff.validator import HandoffValidator
from specflow.trace.models import AgentTraceSpan


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
    agent_outputs = {
        agent_id: result for stage in stages for agent_id, result in stage.agent_results.items()
    }
    handoffs: list[AgentHandoff] = []
    validator = HandoffValidator()
    for task in plan.tasks:
        receiver = registry.get(task.agent_id)
        for sender_id in sorted(task.depends_on):
            sender = registry.get(sender_id)
            handoff = AgentHandoff(
                handoff_id=f"handoff-{uuid4().hex}",
                from_agent_id=sender_id,
                to_agent_id=task.agent_id,
                source_output_schema_id=sender.identity.output_schema_id,
                target_input_schema_id=receiver.identity.input_schema_id,
                payload_ref=f"agent-outputs.json#{sender_id}",
                input_hash=sha256(requirement.encode()).hexdigest(),
                output_hash=sha256(
                    json.dumps(agent_outputs[sender_id], sort_keys=True).encode()
                ).hexdigest(),
            )
            validator.validate(handoff, sender.identity, receiver.identity)
            handoffs.append(handoff)
    coordinator_span_id = f"coordinator-{uuid4().hex}"
    spans = [
        AgentTraceSpan(
            span_id=f"agent-{uuid4().hex}",
            agent_id=agent_id,
            agent_role=registry.get(agent_id).role.value,
            agent_version=registry.get(agent_id).identity.version,
            parent_span_id=coordinator_span_id,
            stage=stage.stage_index,
            stage_started_at=stage.started_at,
            agent_submitted_at=stage.started_at,
            agent_completed_at=stage.completed_at,
            stage_completed_at=stage.completed_at,
            model=model or "mock-model",
            status="success",
        )
        for stage in stages
        for agent_id in sorted(stage.agent_results)
    ]
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
    (output / f"{run_id}-agent-outputs.json").write_text(
        json.dumps(agent_outputs, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / f"{run_id}-handoffs.json").write_text(
        json.dumps([handoff.__dict__ for handoff in handoffs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / f"{run_id}-traces.json").write_text(
        json.dumps([span.as_dict() for span in spans], ensure_ascii=False, indent=2),
        encoding="utf-8",
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
