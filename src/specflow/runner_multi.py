"""Executable, deterministic MVP runner for the fixed six-agent topology."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from specflow.agents.adapter import AgentRunner
from specflow.agents.design import DesignAgent
from specflow.agents.registry import AgentRegistry
from specflow.agents.repository_analyst import RepositoryAnalystAgent
from specflow.agents.review import ReviewAgent
from specflow.agents.risk_review import RiskReviewAgent
from specflow.agents.synthesis import SynthesisAgent
from specflow.agents.test_strategy import TestStrategyAgent
from specflow.coordinator.coordinator import Coordinator
from specflow.coordinator.scheduler import MultiAgentScheduler, StageExecutionResult
from specflow.coordinator.state_machine import MultiAgentWorkflowState
from specflow.handoff.models import AgentHandoff
from specflow.handoff.validator import HandoffValidator
from specflow.llm import LLMClient, OpenAICompatibleConfig, OpenAICompatibleLLMClient
from specflow.trace.models import AgentTraceSpan

AgentExecutor = Callable[[dict[str, Any]], dict[str, Any]]


def run_multi_agent(
    *,
    repo: Path,
    requirement: str,
    output: Path,
    mock: bool = False,
    provider: str = "mock",
    model: str = "mock-model",
    _executor_overrides: Mapping[str, AgentExecutor] | None = None,
) -> int:
    """Execute the fixed plan and persist auditable multi-agent artifacts.

    ``_executor_overrides`` is intentionally test-only injection: it lets the
    runtime contract prove REJECT → one revision → re-review without a network
    provider or a special production-only branch.
    """
    if not repo.is_dir() or not requirement.strip():
        return 2

    run_id = f"run-multi-{sha256(f'{repo.resolve()}|{requirement}'.encode()).hexdigest()[:12]}"
    if (output / run_id).exists():
        return 3

    registry = _build_registry()

    # Create LLM client: real provider or mock
    llm_client: object
    if mock or provider == "mock":
        llm_client = _make_mock_llm_client()
    else:
        try:
            llm_client = _create_real_llm_client(provider, model)
        except Exception:
            return 2

    coordinator = Coordinator(
        agent_registry=registry,
        llm_client=llm_client,
        model=model,
        provider=provider,
    )
    plan = coordinator.plan(run_id)

    # Build executors: AgentRunner for real, raw agent.execute for mock
    executors: dict[str, AgentExecutor] = {}
    for identity in registry.list_agents():
        agent = registry.get(identity.agent_id)
        if mock or provider == "mock":
            executors[identity.agent_id] = agent.execute
        else:
            runner = AgentRunner(
                identity=identity,
                llm_client=llm_client,
                system_prompt=(
                    f"You are the **{identity.role.value}** agent. "
                    f"{identity.description}"
                ),
                model=model,
                temperature=0.0,
                max_tokens=2048,
            )
            executors[identity.agent_id] = runner.execute
    executors.update(_executor_overrides or {})
    base_context: dict[str, Any] = {
        "run_id": run_id,
        "repository_root": str(repo.resolve()),
        "requirement": requirement,
    }
    scheduler = MultiAgentScheduler()
    prior_outputs: dict[str, dict[str, Any]] = {}
    stages: list[StageExecutionResult] = []
    runtime_handoffs: list[AgentHandoff] = []
    revision_exhausted = False

    try:
        coordinator.engine.transition(MultiAgentWorkflowState.PLANNING, "plan compiled")
        coordinator.engine.transition(MultiAgentWorkflowState.ANALYZING, "repository analysis")
        _run_and_accumulate(
            stages, scheduler, plan.stages[0], 0, executors, base_context, prior_outputs
        )
        coordinator.engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "specialists")
        runtime_handoffs.extend(
            _validate_stage_inputs(plan.tasks, plan.stages[1], registry, prior_outputs, requirement)
        )
        _run_and_accumulate(
            stages, scheduler, plan.stages[1], 1, executors, base_context, prior_outputs
        )
        coordinator.engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "synthesis")
        runtime_handoffs.extend(
            _validate_stage_inputs(plan.tasks, plan.stages[2], registry, prior_outputs, requirement)
        )
        _run_and_accumulate(
            stages, scheduler, plan.stages[2], 2, executors, base_context, prior_outputs
        )
        coordinator.engine.transition(MultiAgentWorkflowState.REVIEWING, "review")
        runtime_handoffs.extend(
            _validate_stage_inputs(plan.tasks, plan.stages[3], registry, prior_outputs, requirement)
        )
        _run_and_accumulate(
            stages, scheduler, plan.stages[3], 3, executors, base_context, prior_outputs
        )

        decision = _review_decision(prior_outputs, plan.stages[3][0])
        if decision == "REJECT":
            controller = coordinator.revision_controller
            if controller is None:
                raise RuntimeError("Coordinator did not initialize RevisionController")
            target_id = _revision_target(prior_outputs, plan.stages[3][0])
            target = registry.get(target_id)
            revision_task = controller.create_revision_task(
                target_id,
                target.role,
                "Review rejected the initial synthesis.",
                "Revise the output to address the recorded review finding.",
            )
            if revision_task is None:
                revision_exhausted = True
            else:
                coordinator.engine.transition(MultiAgentWorkflowState.REVISING, "review rejected")
                _run_and_accumulate(
                    stages,
                    scheduler,
                    (target_id,),
                    4,
                    executors,
                    {**base_context, "revision_task": revision_task.__dict__},
                    prior_outputs,
                )
                coordinator.engine.transition(
                    MultiAgentWorkflowState.SYNTHESIZING, "revision complete"
                )
                _run_and_accumulate(
                    stages, scheduler, plan.stages[2], 5, executors, base_context, prior_outputs
                )
                coordinator.engine.transition(MultiAgentWorkflowState.REVIEWING, "re-review")
                _run_and_accumulate(
                    stages, scheduler, plan.stages[3], 6, executors, base_context, prior_outputs
                )
                decision = _review_decision(prior_outputs, plan.stages[3][0])
                revision_exhausted = decision == "REJECT" and controller.exhausted

        coordinator.engine.transition(
            MultiAgentWorkflowState.COMPLETED,
            "review passed" if decision == "PASS" else "revision limit reached",
        )
    except Exception:
        if coordinator.engine.state not in {
            MultiAgentWorkflowState.COMPLETED,
            MultiAgentWorkflowState.FAILED,
        }:
            coordinator.engine.transition(
                MultiAgentWorkflowState.FAILED, "runtime execution failure"
            )
        return 3

    run_dir = output / run_id
    if run_dir.exists():
        return 3
    run_dir.mkdir(parents=True, exist_ok=False)
    agent_outputs = {
        _output_ref(stage.stage_index, agent_id): result
        for stage in stages
        for agent_id, result in stage.agent_results.items()
    }
    handoffs = runtime_handoffs
    traces = _build_trace_tree(stages, registry, run_id, model, coordinator.engine.state.value)
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
        "revision_count": coordinator.engine.revision_count,
        "revision_exhausted": revision_exhausted,
        "stage_results": [
            {"stage": result.stage_index, "agents": sorted(result.agent_results)}
            for result in stages
        ],
        "artifacts": {
            "agent_outputs": "agent-outputs.json",
            "handoffs": "handoffs.json",
            "traces": "traces.json",
        },
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "agent-outputs.json").write_text(
        json.dumps(agent_outputs, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (run_dir / "handoffs.json").write_text(
        json.dumps([handoff.__dict__ for handoff in handoffs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "traces.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


def _build_registry() -> AgentRegistry:
    registry = AgentRegistry()
    for agent in (
        RepositoryAnalystAgent(),
        DesignAgent(),
        TestStrategyAgent(),
        RiskReviewAgent(),
        SynthesisAgent(),
        ReviewAgent(),
    ):
        registry.register(agent)
    return registry


def _run_and_accumulate(
    results: list[StageExecutionResult],
    scheduler: MultiAgentScheduler,
    agent_ids: tuple[str, ...],
    stage_index: int,
    executors: Mapping[str, AgentExecutor],
    context: Mapping[str, Any],
    prior_outputs: dict[str, dict[str, Any]],
) -> None:
    result = scheduler.execute(
        (agent_ids,), dict(executors), {**context, "prior_outputs": dict(prior_outputs)}
    )[0]
    result = replace(result, stage_index=stage_index)
    results.append(result)
    prior_outputs.update(result.agent_results)


def _review_decision(outputs: Mapping[str, dict[str, Any]], review_id: str) -> str:
    output = outputs.get(review_id, {}).get("output", {})
    decision = output.get("decision") if isinstance(output, dict) else None
    if decision not in {"PASS", "REJECT"}:
        raise ValueError("Review agent must return explicit PASS or REJECT decision")
    return decision


def _revision_target(outputs: Mapping[str, dict[str, Any]], review_id: str) -> str:
    output = outputs.get(review_id, {}).get("output", {})
    target = output.get("target_agent_id") if isinstance(output, dict) else None
    return target if isinstance(target, str) and target.strip() else "design-agent-v1"


def _validate_stage_inputs(
    tasks,
    agent_ids: tuple[str, ...],
    registry: AgentRegistry,
    prior_outputs: Mapping[str, dict[str, Any]],
    requirement: str,
) -> list[AgentHandoff]:
    handoffs: list[AgentHandoff] = []
    validator = HandoffValidator()
    task_by_id = {task.agent_id: task for task in tasks}
    for agent_id in agent_ids:
        task = task_by_id[agent_id]
        receiver = registry.get(task.agent_id)
        for sender_id in sorted(task.depends_on):
            sender = registry.get(sender_id)
            sender_stage = task_by_id[sender_id].stage
            payload_ref = _output_ref(sender_stage, sender_id)
            payload = prior_outputs.get(sender_id)
            if payload is None:
                raise ValueError(f"Missing runtime output for handoff sender {sender_id}")
            handoff = AgentHandoff(
                handoff_id=f"handoff-{uuid4().hex}",
                from_agent_id=sender_id,
                to_agent_id=task.agent_id,
                source_output_schema_id=sender.identity.output_schema_id,
                target_input_schema_id=receiver.identity.input_schema_id,
                payload_ref=f"agent-outputs.json#{payload_ref}",
                input_hash=sha256(requirement.encode()).hexdigest(),
                output_hash=sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            )
            validator.validate(handoff, sender.identity, receiver.identity)
            validator.validate_payload(handoff, sender.identity, {payload_ref: payload})
            handoffs.append(handoff)
    return handoffs


def _output_ref(stage_index: int, agent_id: str) -> str:
    return f"stage-{stage_index}/{agent_id}"


def _build_trace_tree(
    stages, registry, run_id: str, model: str, status: str
) -> list[dict[str, object]]:
    root_id = f"run-{uuid4().hex}"
    coordinator_id = f"coordinator-{uuid4().hex}"
    traces: list[dict[str, object]] = [
        {
            "span_id": root_id,
            "parent_span_id": None,
            "kind": "run",
            "run_id": run_id,
            "status": status,
        },
        {
            "span_id": coordinator_id,
            "parent_span_id": root_id,
            "kind": "coordinator",
            "run_id": run_id,
            "status": status,
        },
    ]
    revision_span_id = (
        f"revision-{uuid4().hex}" if any(s.stage_index == 4 for s in stages) else None
    )
    if revision_span_id is not None:
        traces.append(
            {
                "span_id": revision_span_id,
                "parent_span_id": coordinator_id,
                "kind": "revision",
                "run_id": run_id,
                "status": status,
            }
        )
    for stage in stages:
        for agent_id in sorted(stage.agent_results):
            timing = stage.agent_timings[agent_id]
            span = AgentTraceSpan(
                span_id=f"agent-{uuid4().hex}",
                agent_id=agent_id,
                agent_role=registry.get(agent_id).role.value,
                agent_version=registry.get(agent_id).identity.version,
                parent_span_id=revision_span_id if stage.stage_index == 4 else coordinator_id,
                stage=stage.stage_index,
                stage_started_at=stage.started_at,
                agent_submitted_at=timing.submitted_at,
                agent_completed_at=timing.completed_at,
                stage_completed_at=stage.completed_at,
                model=model or "mock-model",
                status="success",
                revision_round=1 if stage.stage_index >= 4 else 0,
            )
            traces.append(span.as_dict())
    return traces


def _make_mock_llm_client() -> object:
    """Create a deterministic client for mock execution."""

    class MockClient:
        def complete(self, request) -> object:
            class MockResponse:
                content = (
                    '{"task_description":"mock","analysis_focus":[],"evaluation_hints":[], '
                    '"repository_scope_hint":""}'
                )

            return MockResponse()

    return MockClient()


def _create_real_llm_client(provider: str, model: str) -> LLMClient:
    """Create a real OpenAI-compatible LLM client from env vars."""
    config = OpenAICompatibleConfig.from_env()
    return OpenAICompatibleLLMClient(config)
