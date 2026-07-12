"""Executable, deterministic MVP runner for the fixed six-agent topology."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
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
from specflow.evaluation.metrics import AgentMetrics, RunMetrics
from specflow.evidence import EvidenceCollector
from specflow.evidence.models import EvidenceCollectionConfig
from specflow.handoff.models import AgentHandoff
from specflow.handoff.validator import HandoffValidator
from specflow.llm import LLMClient, OpenAICompatibleConfig, OpenAICompatibleLLMClient
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.policy import DEFAULT_POLICY, ExecutionPolicy, PolicyValidator, RuntimeGuard
from specflow.tools import ToolExecutor, ToolRegistry
from specflow.tools.repository_tools import RepositoryToolSet
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
    policy: ExecutionPolicy = DEFAULT_POLICY,
    _executor_overrides: Mapping[str, AgentExecutor] | None = None,
) -> int:
    """Execute the fixed plan and persist auditable multi-agent artifacts.

    ``_executor_overrides`` is intentionally test-only injection: it lets the
    runtime contract prove REJECT → one revision → re-review without a network
    provider or a special production-only branch.
    """
    started_at = datetime.now(UTC).isoformat()
    t0 = time.monotonic()

    PolicyValidator().validate(policy)
    guard = RuntimeGuard(policy)

    if not repo.is_dir() or not requirement.strip():
        return 2

    run_id = f"run-multi-{sha256(f'{repo.resolve()}|{requirement}'.encode()).hexdigest()[:12]}"
    if (output / run_id).exists():
        return 3

    # Collect repository evidence (same pipeline as legacy runner)
    evidence_text = ""
    tool_call_records: list[dict[str, Any]] = []
    discovered_files = 0
    selected_file_count = 0
    referenced_file_count = 0
    try:
        tool_registry = ToolRegistry()
        RepositoryToolSet(repo).register_into(tool_registry)
        tool_executor = ToolExecutor(tool_registry)
        collector = EvidenceCollector(
            tool_executor,
            repo,
            config=EvidenceCollectionConfig(
                max_selected_files=min(10, policy.repository.max_selected_files),
                max_total_evidence_chars=policy.repository.max_total_evidence_chars,
                max_tool_calls=20,
            ),
        )
        evidence = collector.collect(
            run_id=run_id,
            requirement=requirement,
            project_summary=_repo_summary(repo),
            technology_stack=(),
        )
        evidence_text = evidence.serialized_context()
        tool_call_records = [
            r.as_dict() if hasattr(r, "as_dict") else asdict(r) for r in evidence.tool_call_records
        ]
        discovered_files = evidence.discovered_file_count
        selected_file_count = len(evidence.selected_files)
        referenced_file_count = len({excerpt.relative_path for excerpt in evidence.excerpts})
    except Exception:
        # Evidence is a required, untrusted input boundary.  Continuing would
        # let agents produce an ungrounded plan with no audit evidence.
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
            import sys

            print("Provider configuration error", file=sys.stderr)
            return 2

    # Build schema registry before Coordinator so PlanValidator can check schema IDs.
    from specflow.schema import build_schema_registry

    schema_registry = build_schema_registry()

    coordinator = Coordinator(
        agent_registry=registry,
        llm_client=llm_client,
        model=model,
        provider=provider,
        schema_registry=schema_registry,
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
                schema_registry=schema_registry,
                system_prompt=(
                    f"You are the **{identity.role.value}** agent. {identity.description}"
                ),
                model=model,
                temperature=0.0,
                max_tokens=2048,
            )
            executors[identity.agent_id] = runner.execute
    executors.update(_executor_overrides or {})
    base_context: dict[str, Any] = {
        "run_id": run_id,
        "requirement": requirement,
        "repository_evidence": evidence_text,
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
            stages,
            scheduler,
            plan.stages[0],
            0,
            executors,
            base_context,
            prior_outputs,
            registry,
            schema_registry,
            guard,
        )
        coordinator.engine.transition(MultiAgentWorkflowState.EXECUTING_SPECIALISTS, "specialists")
        runtime_handoffs.extend(
            _validate_stage_inputs(plan.tasks, plan.stages[1], registry, prior_outputs, requirement)
        )
        _run_and_accumulate(
            stages,
            scheduler,
            plan.stages[1],
            1,
            executors,
            base_context,
            prior_outputs,
            registry,
            schema_registry,
            guard,
        )
        coordinator.engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "synthesis")
        runtime_handoffs.extend(
            _validate_stage_inputs(plan.tasks, plan.stages[2], registry, prior_outputs, requirement)
        )
        _run_and_accumulate(
            stages,
            scheduler,
            plan.stages[2],
            2,
            executors,
            base_context,
            prior_outputs,
            registry,
            schema_registry,
            guard,
        )
        coordinator.engine.transition(MultiAgentWorkflowState.REVIEWING, "review")
        runtime_handoffs.extend(
            _validate_stage_inputs(plan.tasks, plan.stages[3], registry, prior_outputs, requirement)
        )
        _run_and_accumulate(
            stages,
            scheduler,
            plan.stages[3],
            3,
            executors,
            base_context,
            prior_outputs,
            registry,
            schema_registry,
            guard,
        )

        decision = _review_decision(prior_outputs, plan.stages[3][0])
        if decision == "REJECT":
            guard.consume_revision()
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
                runtime_handoffs.append(
                    _revision_handoff(
                        review_id=plan.stages[3][0],
                        target_id=target_id,
                        registry=registry,
                        prior_outputs=prior_outputs,
                        requirement=requirement,
                    )
                )
                _run_and_accumulate(
                    stages,
                    scheduler,
                    (target_id,),
                    4,
                    executors,
                    {**base_context, "revision_task": revision_task.__dict__},
                    prior_outputs,
                    registry,
                    schema_registry,
                    guard,
                )
                coordinator.engine.transition(
                    MultiAgentWorkflowState.SYNTHESIZING, "revision complete"
                )
                runtime_handoffs.extend(
                    _validate_stage_inputs(
                        plan.tasks,
                        plan.stages[2],
                        registry,
                        prior_outputs,
                        requirement,
                        sender_stage_overrides={target_id: 4},
                    )
                )
                _run_and_accumulate(
                    stages,
                    scheduler,
                    plan.stages[2],
                    5,
                    executors,
                    base_context,
                    prior_outputs,
                    registry,
                    schema_registry,
                    guard,
                )
                coordinator.engine.transition(MultiAgentWorkflowState.REVIEWING, "re-review")
                runtime_handoffs.extend(
                    _validate_stage_inputs(
                        plan.tasks,
                        plan.stages[3],
                        registry,
                        prior_outputs,
                        requirement,
                        sender_stage_overrides={"synthesis-agent-v1": 5},
                    )
                )
                _run_and_accumulate(
                    stages,
                    scheduler,
                    plan.stages[3],
                    6,
                    executors,
                    base_context,
                    prior_outputs,
                    registry,
                    schema_registry,
                    guard,
                )
                decision = _review_decision(prior_outputs, plan.stages[3][0])
                revision_exhausted = decision == "REJECT" and controller.exhausted

        coordinator.engine.transition(
            MultiAgentWorkflowState.COMPLETED,
            "review passed" if decision == "PASS" else "revision limit reached",
        )
    except Exception:
        _persist_failed_run(
            output=output,
            run_id=run_id,
            coordinator=coordinator,
            registry=registry,
            model=model,
            stages=stages,
            plan=plan,
            discovered_files=discovered_files,
            error="MULTI_AGENT_RUN_FAILED",
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
    policy_hash = policy.policy_hash()
    idempotency_key = sha256(
        f"{sha256(repo.resolve().as_uri().encode()).hexdigest()}"
        f"|{sha256(requirement.encode()).hexdigest()}"
        f"|{plan.structure_hash}"
        f"|{policy_hash}"
        f"|{provider}|{model}".encode()
    ).hexdigest()

    manifest = {
        "run_id": run_id,
        "idempotency_key": idempotency_key,
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
            "sources": "sources.json",
            "metrics": "metrics.json",
        },
        "discovered_files": discovered_files,
        "tool_call_count": len(tool_call_records),
        "execution_policy": {
            "policy_version": policy.policy_version,
            "max_wall_time_seconds": policy.max_wall_time_seconds,
            "max_llm_calls": policy.max_llm_calls,
            "max_revisions": policy.max_revisions,
        },
        "execution_policy_hash": policy_hash,
        "budget_usage": {
            "llm_calls": guard.llm_calls,
            "input_tokens": guard.total_input_tokens,
            "output_tokens": guard.total_output_tokens,
            "revision_count": guard.revision_count,
        },
    }
    # Write stage checkpoints
    checkpoints = [
        {
            "stage": s.stage_index,
            "agents": sorted(s.agent_results),
            "started": s.started_at,
            "completed": s.completed_at,
        }
        for s in stages
    ]
    (run_dir / "checkpoints.json").write_text(
        json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
    (run_dir / "sources.json").write_text(
        json.dumps(
            {"evidence": evidence_text, "tool_calls": tool_call_records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    # Persist unified metrics for A/B comparison
    wall_ms = int((time.monotonic() - t0) * 1000)
    metrics = _build_multi_agent_metrics(
        plan=plan,
        stages=stages,
        coordinator=coordinator,
        started_at=started_at,
        wall_ms=wall_ms,
        discovered_files=discovered_files,
        tool_call_count=len(tool_call_records),
        selected_file_count=selected_file_count,
        referenced_file_count=referenced_file_count,
        runtime_handoffs=runtime_handoffs,
        revision_exhausted=revision_exhausted,
        provider=provider,
        model=model,
    )
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
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
    registry: AgentRegistry,
    schema_registry: object,
    guard: RuntimeGuard,
) -> None:
    guard.check_wall_time()
    validated_inputs = _validated_inputs(
        agent_ids, registry, schema_registry, context, prior_outputs
    )
    guarded_executors = {
        agent_id: _budgeted_executor(executors[agent_id], validated_inputs[agent_id], guard)
        for agent_id in agent_ids
    }
    result = scheduler.execute(
        (agent_ids,), guarded_executors, {**context, "prior_outputs": dict(prior_outputs)}
    )[0]
    result = replace(result, stage_index=stage_index)
    _validate_stage_results(result, registry, schema_registry)
    results.append(result)
    prior_outputs.update(result.agent_results)


def _budgeted_executor(
    executor: AgentExecutor, validated_input: dict[str, Any], guard: RuntimeGuard
) -> AgentExecutor:
    def run(context: dict[str, Any]) -> dict[str, Any]:
        guard.consume_llm_call()
        guard.check_wall_time()
        result = executor({**context, "validated_input": validated_input})
        usage = result.get("usage", {})
        guard.consume_tokens(
            usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        )
        return result

    return run


def _validated_inputs(
    agent_ids: tuple[str, ...],
    registry: AgentRegistry,
    schema_registry: object,
    context: Mapping[str, Any],
    prior_outputs: Mapping[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build and validate only the declared input contract for each receiver."""
    output = {agent_id: result.get("output", {}) for agent_id, result in prior_outputs.items()}
    requirement = str(context.get("requirement", ""))
    evidence = str(context.get("repository_evidence", ""))
    inputs: dict[str, dict[str, Any]] = {}
    for agent_id in agent_ids:
        role = registry.get(agent_id).role.value
        if role == "repository_analyst":
            payload = {"requirement": requirement, "repository_evidence": evidence}
        elif role in {"design", "test_strategy", "risk_review"}:
            payload = {
                "requirement": requirement,
                "repository_analysis": output.get("repository-analyst-agent-v1", {}),
            }
        elif role == "synthesis":
            payload = {
                "requirement": requirement,
                "design_output": output.get("design-agent-v1", {}),
                "test_strategy_output": output.get("test-strategy-agent-v1", {}),
                "risk_review_output": output.get("risk-review-agent-v1", {}),
            }
        elif role == "review":
            payload = {
                "requirement": requirement,
                "synthesis_output": output.get("synthesis-agent-v1", {}),
            }
        else:
            raise ValueError("UNKNOWN_AGENT_ROLE")
        model = schema_registry.get(registry.get(agent_id).identity.input_schema_id)
        inputs[agent_id] = model.model_validate(payload).model_dump()
    return inputs


def _validate_stage_results(
    stage: StageExecutionResult,
    registry: AgentRegistry,
    schema_registry: object,
) -> None:
    """Fail closed before outputs can become inter-agent handoffs."""
    for agent_id, result in stage.agent_results.items():
        if result.get("agent_id") != agent_id or not result.get("success", True):
            raise ValueError("AGENT_EXECUTION_FAILED")
        output = _sanitize_artifact_value(result.get("output"))
        if not isinstance(output, dict):
            raise ValueError("AGENT_OUTPUT_NOT_OBJECT")
        identity = registry.get(agent_id).identity
        try:
            output_model = schema_registry.get(identity.output_schema_id)
            result["output"] = output_model.model_validate(output).model_dump()
        except Exception as exc:
            raise ValueError("SCHEMA_VALIDATION_FAILED") from exc
        result["schema_validated"] = True


_ABSOLUTE_PATH_RE = re.compile(r"(?<!\w)(?:[A-Za-z]:[\\/]|/)[^\s\"']+")
_SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+")


def _sanitize_artifact_value(value: object) -> object:
    """Remove secrets and absolute filesystem paths before persistence/handoff."""
    if isinstance(value, str):
        value = _SECRET_RE.sub(r"\1=<redacted>", value)
        return _ABSOLUTE_PATH_RE.sub("<absolute-path-redacted>", value)
    if isinstance(value, list):
        return [_sanitize_artifact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize_artifact_value(item) for key, item in value.items()}
    return value


def _review_decision(outputs: Mapping[str, dict[str, Any]], review_id: str) -> str:
    """Extract PASS/REJECT decision from review agent output.

    Accepts multiple LLM response formats and normalizes Chinese decisions.
    """
    output = outputs.get(review_id, {}).get("output", {})
    if not isinstance(output, dict):
        raise ValueError("Review agent output must be a dict")

    value = output.get("decision")
    if value in {"PASS", "REJECT"}:
        return value
    raise ValueError("Review agent output must contain explicit PASS or REJECT decision")


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
    sender_stage_overrides: Mapping[str, int] | None = None,
) -> list[AgentHandoff]:
    handoffs: list[AgentHandoff] = []
    validator = HandoffValidator()
    task_by_id = {task.agent_id: task for task in tasks}
    for agent_id in agent_ids:
        task = task_by_id[agent_id]
        receiver = registry.get(task.agent_id)
        for sender_id in sorted(task.depends_on):
            sender = registry.get(sender_id)
            sender_stage = (sender_stage_overrides or {}).get(
                sender_id, task_by_id[sender_id].stage
            )
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
                output_hash=sha256(canonical_json_bytes(payload)).hexdigest(),
            )
            validator.validate(handoff, sender.identity, receiver.identity)
            validator.validate_payload(handoff, sender.identity, {payload_ref: payload})
            handoffs.append(handoff)
    return handoffs


def _revision_handoff(
    *,
    review_id: str,
    target_id: str,
    registry: AgentRegistry,
    prior_outputs: Mapping[str, dict[str, Any]],
    requirement: str,
) -> AgentHandoff:
    """Record the explicit Review → revision-target audit edge."""
    review = prior_outputs[review_id]
    sender = registry.get(review_id).identity
    receiver = registry.get(target_id).identity
    handoff = AgentHandoff(
        handoff_id=f"handoff-revision-{uuid4().hex}",
        from_agent_id=review_id,
        to_agent_id=target_id,
        source_output_schema_id=sender.output_schema_id,
        target_input_schema_id=receiver.input_schema_id,
        payload_ref="agent-outputs.json#stage-3/review-agent-v1",
        input_hash=sha256(requirement.encode()).hexdigest(),
        output_hash=sha256(canonical_json_bytes(review)).hexdigest(),
    )
    validator = HandoffValidator()
    validator.validate(handoff, sender, receiver)
    validator.validate_payload(handoff, sender, {"stage-3/review-agent-v1": review})
    return handoff


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
            result = stage.agent_results[agent_id]
            if not result.get("success", False):
                trace_status = "failed"
            elif result.get("degraded", False):
                trace_status = "degraded"
            else:
                trace_status = "success"
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
                status=trace_status,
                revision_round=1 if stage.stage_index >= 4 else 0,
            )
            traces.append(span.as_dict())
    return traces


def _safe_write(
    run_dir: Path,
    filename: str,
    data: object,
    guard: RuntimeGuard,
    *,
    sort_keys: bool = False,
) -> None:
    """Write artifact with size check before touching disk."""
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort_keys)
    guard.check_artifact_size(len(content.encode("utf-8")))
    (run_dir / filename).write_text(content, encoding="utf-8")


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


def _persist_failed_run(
    output: Path,
    run_id: str,
    coordinator: Coordinator,
    registry: AgentRegistry,
    model: str,
    stages: list[StageExecutionResult],
    plan: object,
    discovered_files: int,
    error: str,
) -> None:
    """Persist FAILED manifest, state history, and partial traces for audit."""
    try:
        if coordinator.engine.state not in {
            MultiAgentWorkflowState.COMPLETED,
            MultiAgentWorkflowState.FAILED,
        }:
            coordinator.engine.transition(
                MultiAgentWorkflowState.FAILED, f"runtime failure: {error}"
            )
    except Exception:
        # State transition recording is best-effort — do not mask the
        # original runtime failure.
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("Failed to record workflow failure state", exc_info=True)

    try:
        run_dir = output / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        traces = _build_trace_tree(stages, registry, run_id, model, "failed")
        failed_manifest = {
            "run_id": run_id,
            "plan_id": getattr(plan, "plan_id", "unknown"),
            "workflow_state": "failed",
            "workflow_history": list(coordinator.engine.history),
            "error": error,
            "stages_completed": len(stages),
            "discovered_files": discovered_files,
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(failed_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (run_dir / "traces.json").write_text(
            json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Persist partial agent outputs for debugging
        agent_outputs = {
            f"stage-{s.stage_index}/{aid}": result
            for s in stages
            for aid, result in s.agent_results.items()
        }
        (run_dir / "agent-outputs.json").write_text(
            json.dumps(agent_outputs, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        # Artifact persistence is best-effort — don't hide the original error.
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("Failed to persist failed-run artifacts", exc_info=True)


def _build_multi_agent_metrics(
    plan: object,
    stages: list[StageExecutionResult],
    coordinator: Coordinator,
    started_at: str,
    wall_ms: int,
    discovered_files: int,
    tool_call_count: int,
    selected_file_count: int,
    referenced_file_count: int,
    runtime_handoffs: list[AgentHandoff],
    revision_exhausted: bool,
    provider: str,
    model: str,
) -> RunMetrics:
    """Build unified RunMetrics from multi-agent execution data."""
    agent_metrics: list[AgentMetrics] = []
    total_in = 0
    total_out = 0
    fallback_count = 0
    degraded_count = 0
    schema_ok = 0
    schema_fail = 0

    for stage in stages:
        for agent_id, result in stage.agent_results.items():
            usage = result.get("usage", {})
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            total_in += tokens_in
            total_out += tokens_out

            degraded = result.get("degraded", False)
            if degraded:
                degraded_count += 1
            if not result.get("success", True):
                fallback_count += 1
            if result.get("schema_validated", False):
                schema_ok += 1
            else:
                schema_fail += 1

            agent_metrics.append(
                AgentMetrics(
                    agent_id=agent_id,
                    role=result.get("role", "unknown"),
                    stage=stage.stage_index,
                    duration_ms=_agent_wall_ms(stage, agent_id),
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                    llm_call_success=result.get("success", True),
                    fallback_used=not result.get("success", True),
                    degraded=degraded,
                    schema_validated=result.get("schema_validated", False),
                )
            )

    # Compute parallel speedup for stage 1 (specialists)
    parallel_theoretical = 0
    parallel_actual = 0
    for am in agent_metrics:
        if am.stage == 1:
            parallel_theoretical += am.duration_ms
            if am.duration_ms > parallel_actual:
                parallel_actual = am.duration_ms
    parallel_speedup = (
        parallel_theoretical / parallel_actual
        if parallel_actual > 0 and parallel_theoretical > 0
        else 0.0
    )

    # Determine status
    state = coordinator.engine.state.value if hasattr(coordinator.engine, "state") else "unknown"
    if state == "completed":
        status = "completed"
    elif state == "failed":
        status = "failed"
    else:
        status = "degraded"

    review_agent_id = plan.stages[-1][0] if hasattr(plan, "stages") else ""
    decision = _review_decision(
        next(
            stage.agent_results
            for stage in reversed(stages)
            if review_agent_id in stage.agent_results
        ),
        review_agent_id,
    )

    return RunMetrics(
        mode="multi-agent",
        provider=provider,
        model=model,
        status=status,
        started_at=started_at,
        completed_at=datetime.now(UTC).isoformat(),
        wall_time_ms=wall_ms,
        input_tokens=total_in,
        output_tokens=total_out,
        total_tokens=total_in + total_out,
        llm_call_count=len(agent_metrics),
        fallback_count=fallback_count,
        degraded_count=degraded_count,
        schema_validated_count=schema_ok,
        schema_unvalidated_count=schema_fail,
        discovered_file_count=discovered_files,
        selected_file_count=selected_file_count,
        referenced_file_count=referenced_file_count,
        tool_call_count=tool_call_count,
        revision_count=coordinator.engine.revision_count,
        revision_exhausted=revision_exhausted,
        review_decision=decision,
        agent_count=len(agent_metrics),
        stage_count=len(plan.stages) if hasattr(plan, "stages") else 0,
        parallel_stage_count=1,
        handoff_count=len(runtime_handoffs),
        agent_metrics=agent_metrics,
        parallel_theoretical_ms=parallel_theoretical,
        parallel_actual_ms=parallel_actual,
        parallel_speedup=round(parallel_speedup, 2),
    )


def _agent_wall_ms(stage: StageExecutionResult, agent_id: str) -> int:
    """Compute wall-clock duration for one agent from stage timing data."""
    timing = stage.agent_timings.get(agent_id)
    if timing is None or not timing.submitted_at or not timing.completed_at:
        return 0
    try:
        from datetime import datetime as dt

        start = dt.fromisoformat(timing.submitted_at)
        end = dt.fromisoformat(timing.completed_at)
        return int((end - start).total_seconds() * 1000)
    except (ValueError, TypeError):
        return 0


def _repo_summary(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        return f"Python project with pyproject.toml at {repo.name}"
    return f"Project at {repo.name}"


def _create_real_llm_client(provider: str, model: str) -> LLMClient:
    """Create a real OpenAI-compatible LLM client from env vars."""
    config = OpenAICompatibleConfig.from_env()
    return OpenAICompatibleLLMClient(config)
