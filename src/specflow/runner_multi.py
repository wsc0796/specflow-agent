"""Executable, deterministic MVP runner for the fixed six-agent topology."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Lock
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
from specflow.evidence.models import EvidenceBundle, EvidenceCollectionConfig
from specflow.handoff.models import AgentHandoff
from specflow.handoff.validator import HandoffValidator
from specflow.llm import LLMClient, OpenAICompatibleConfig, OpenAICompatibleLLMClient
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.plan.models import (
    AgentTask,
    ControlledEvidenceSummary,
    EffectiveDelegationPlan,
    EvidenceReference,
    TaskBriefArtifact,
)
from specflow.policy import (
    DEFAULT_POLICY,
    ExecutionPolicy,
    PolicyValidator,
    RuntimeGuard,
    SpecFlowError,
)
from specflow.revision.models import (
    FindingResolution,
    RevisionContext,
    RevisionInput,
    RevisionResult,
    ValidatedAgentOutput,
)
from specflow.schema.agent_payloads import ReviewPayload
from specflow.schema.models import AgentExecutionInput
from specflow.tools import ToolExecutor, ToolRegistry
from specflow.tools.repository_tools import RepositoryToolSet
from specflow.trace.models import (
    AgentTraceSpan,
    RevisionTraceEvent,
    TaskBriefTraceEvent,
)

AgentExecutor = Callable[[dict[str, Any]], dict[str, Any]]
logger = logging.getLogger(__name__)


class _TaskBriefEventRecorder:
    """Thread-safe in-memory collector persisted with the run trace tree."""

    def __init__(self) -> None:
        self._events: list[TaskBriefTraceEvent] = []
        self._lock = Lock()

    def record(self, event: TaskBriefTraceEvent) -> None:
        with self._lock:
            self._events.append(event)

    def snapshot(self) -> tuple[TaskBriefTraceEvent, ...]:
        order = {"TASK_BRIEF_GENERATED": 0, "TASK_BRIEF_CONSUMED": 1}
        with self._lock:
            return tuple(
                sorted(
                    self._events,
                    key=lambda event: (
                        order[event.event_type],
                        event.stage,
                        event.agent_id,
                        event.trace_id,
                    ),
                )
            )


class _RevisionEventRecorder:
    """Thread-safe in-memory collector for revision lifecycle trace events."""

    def __init__(self) -> None:
        self._events: list[RevisionTraceEvent] = []
        self._lock = Lock()

    def record(self, event: RevisionTraceEvent) -> None:
        with self._lock:
            self._events.append(event)

    def snapshot(self) -> tuple[RevisionTraceEvent, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._events,
                    key=lambda event: (
                        event.round,
                        event.revision_id or "",
                        event.agent_id or "",
                        event.event_type.value,
                        event.trace_id,
                    ),
                )
            )


def _controlled_evidence_summary(evidence: EvidenceBundle) -> ControlledEvidenceSummary:
    """Derive stable, bounded evidence references from the collected evidence bundle."""
    references: dict[str, EvidenceReference] = {}
    for excerpt in evidence.excerpts:
        source_hash = str(evidence.source_hashes.get(excerpt.relative_path, ""))
        identity = {
            "relative_path": excerpt.relative_path,
            "line_number": excerpt.line_number,
            "source_hash": source_hash,
        }
        evidence_id = f"evidence-{sha256(canonical_json_bytes(identity)).hexdigest()[:24]}"
        references[evidence_id] = EvidenceReference(
            evidence_id=evidence_id,
            relative_path=excerpt.relative_path,
            line_number=excerpt.line_number,
            source_hash=source_hash,
        )
    return ControlledEvidenceSummary(
        content=evidence.serialized_context(),
        evidence_hash=evidence.evidence_hash,
        references=tuple(references[key] for key in sorted(references)),
        truncated=evidence.truncated,
    )


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
    _llm_client_override: object | None = None,
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
    guard.set_run_context(run_id, execution_mode="mock" if mock else "live")

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
        evidence_summary = _controlled_evidence_summary(evidence)
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
    guard.set_configured_role_count(len(registry.list_agents()))

    # Create LLM client: real provider or mock
    llm_client: object
    if _llm_client_override is not None:
        llm_client = _llm_client_override
    elif mock or provider == "mock":
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
        guard=guard,
        retry_policy=policy.retry,
    )
    try:
        plan = coordinator.plan(
            run_id,
            requirement=requirement,
            evidence_summary=evidence_summary,
        )
        task_brief_artifact = TaskBriefArtifact.build(
            run_id,
            tuple(task.task_brief for task in plan.tasks),
        )
    except Exception as error:
        logger.error("run %s failed during planning: %s", run_id, type(error).__name__)
        _persist_planning_failure(
            output=output,
            run_id=run_id,
            guard=guard,
            error="PLANNING_FAILED",
        )
        return 3
    task_brief_events = _TaskBriefEventRecorder()
    for task in plan.tasks:
        brief = task.task_brief
        task_brief_events.record(
            TaskBriefTraceEvent(
                event_type="TASK_BRIEF_GENERATED",
                run_id=run_id,
                agent_id=task.agent_id,
                role=task.role,
                brief_hash=brief.brief_hash(),
                schema_version=brief.schema_version,
                status=brief.status,
                stage=task.stage,
                trace_id=brief.provenance.trace_id,
            )
        )

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
                max_tokens=policy.tokens.max_agent_output_tokens,
                task_brief_event_sink=task_brief_events.record,
                budget=guard,
                max_retries=policy.retry.max_provider_retries,
            )
            executors[identity.agent_id] = runner.execute
    executors.update(_executor_overrides or {})
    base_context: dict[str, Any] = {
        "run_id": run_id,
        "requirement": requirement,
        "repository_evidence": evidence_text,
        "evidence_summary": evidence_summary,
    }
    scheduler = MultiAgentScheduler(max_parallel_workers=policy.max_parallel_agents)
    prior_outputs: dict[str, dict[str, Any]] = {}
    stages: list[StageExecutionResult] = []
    runtime_handoffs: list[AgentHandoff] = []
    revision_exhausted = False
    revision_events = _RevisionEventRecorder()

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
            plan.tasks,
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
            plan.tasks,
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
            plan.tasks,
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
            plan.tasks,
            registry,
            schema_registry,
            guard,
        )

        controller = coordinator.revision_controller
        if controller is None:
            raise RuntimeError("Coordinator did not initialize RevisionController")
        review_records: list[dict[str, Any]] = []
        revision_inputs: list[RevisionInput] = []
        revision_results: list[RevisionResult] = []
        revision_stage_by_agent: dict[str, int] = {}
        next_stage = 4

        def record_review(review_id: str, round_label: int) -> ReviewPayload:
            payload = _review_payload(prior_outputs, review_id)
            review_records.append(payload.model_dump(mode="json"))
            revision_events.record(
                RevisionTraceEvent(
                    event_type="REVIEW_FINDINGS_CREATED",
                    run_id=run_id,
                    round=round_label,
                    agent_id=review_id,
                    status=payload.decision,
                    trace_id=str(uuid4()),
                )
            )
            return payload

        decision = _review_decision(prior_outputs, plan.stages[3][0])
        review_payload = record_review(plan.stages[3][0], 0)
        _validate_review_findings(review_payload, plan=plan, evidence_summary=evidence_summary)
        terminal_state: str | None = None

        while decision == "REJECT":
            round_number = controller.begin_round()
            if round_number is None:
                terminal_state = "needs_human_review"
                break
            guard.record_revision_round()
            coordinator.engine.transition(MultiAgentWorkflowState.REVISING, "review rejected")
            targets = _revision_targets(review_payload, plan)
            if not targets:
                raise ValueError("REJECT requires at least one finding target")
            review_artifact_hash = sha256(
                canonical_json_bytes(review_payload.model_dump(mode="json"))
            ).hexdigest()

            for target_id in targets:
                target = registry.get(target_id)
                task = next(task for task in plan.tasks if task.agent_id == target_id)
                findings = tuple(
                    finding
                    for finding in review_payload.findings
                    if finding.target_agent_id == target_id
                )
                if not findings:
                    raise ValueError(f"No findings target {target_id}")
                prior_envelope = prior_outputs.get(target_id)
                if prior_envelope is None:
                    raise ValueError(f"Missing prior output for revision target {target_id}")
                prior_payload = prior_envelope.get("output", {})
                if not isinstance(prior_payload, dict):
                    raise ValueError(f"Prior output for {target_id} is not a dict")
                prior_output_hash = sha256(canonical_json_bytes(prior_payload)).hexdigest()
                validated_prior = ValidatedAgentOutput(
                    agent_id=target_id,
                    schema_id=target.identity.output_schema_id,
                    payload=prior_payload,
                )
                revision_task = controller.create_revision_task(
                    run_id=run_id,
                    round_number=round_number,
                    target_agent_id=target_id,
                    target_role=target.role,
                    finding_ids=tuple(finding.finding_id for finding in findings),
                    prior_output_hash=prior_output_hash,
                )
                if revision_task is None:
                    raise ValueError(f"Revision task could not be created for {target_id}")
                revision_id = revision_task.revision_id
                revision_input = RevisionInput.build(
                    run_id=run_id,
                    revision_id=revision_id,
                    revision_round=round_number,
                    max_revision_rounds=controller.policy.max_total_rounds,
                    target_agent_id=target_id,
                    role=target.role,
                    original_requirement=requirement,
                    verified_evidence=evidence_summary,
                    task_brief=task.task_brief,
                    prior_output=validated_prior,
                    findings=findings,
                    output_schema_id=target.identity.output_schema_id,
                )
                revision_inputs.append(revision_input)
                revision_context = RevisionContext(
                    revision_id=revision_id,
                    revision_round=round_number,
                    max_revision_rounds=revision_input.max_revision_rounds,
                    target_agent_id=target_id,
                    prior_output=validated_prior,
                    prior_output_hash=revision_input.prior_output_hash,
                    findings=findings,
                    parent_artifact="sources.json",
                    review_artifact_hash=review_artifact_hash,
                )
                controller.mark_running(revision_id)
                revision_events.record(
                    RevisionTraceEvent(
                        event_type="REVISION_SCHEDULED",
                        run_id=run_id,
                        revision_id=revision_id,
                        round=round_number,
                        agent_id=target_id,
                        status="scheduled",
                        trace_id=str(uuid4()),
                    )
                )
                revision_events.record(
                    RevisionTraceEvent(
                        event_type="REVISION_STARTED",
                        run_id=run_id,
                        revision_id=revision_id,
                        round=round_number,
                        agent_id=target_id,
                        status="running",
                        trace_id=str(uuid4()),
                    )
                )
                runtime_handoffs.append(
                    _revision_handoff(
                        review_id=plan.stages[3][0],
                        target_id=target_id,
                        registry=registry,
                        prior_outputs=prior_outputs,
                        requirement=requirement,
                    )
                )
                guard.record_revision_agent_invocation()
                _run_and_accumulate(
                    stages,
                    scheduler,
                    (target_id,),
                    next_stage,
                    executors,
                    {**base_context, "revision_context": revision_context},
                    prior_outputs,
                    plan.tasks,
                    registry,
                    schema_registry,
                    guard,
                )
                revision_stage_by_agent[target_id] = next_stage
                next_stage += 1
                revision_result = _parse_revision_result(prior_outputs, target_id, revision_input)
                revision_results.append(revision_result)
                controller.mark_completed(
                    revision_id,
                    result_artifact="revision-results.json",
                )
                revision_events.record(
                    RevisionTraceEvent(
                        event_type="REVISION_COMPLETED",
                        run_id=run_id,
                        revision_id=revision_id,
                        round=round_number,
                        agent_id=target_id,
                        status="completed",
                        trace_id=str(uuid4()),
                    )
                )
                for resolution in revision_result.resolutions:
                    revision_events.record(
                        RevisionTraceEvent(
                            event_type=(
                                "FINDING_RESOLVED"
                                if resolution.status == "resolved"
                                else "FINDING_UNRESOLVED"
                            ),
                            run_id=run_id,
                            revision_id=revision_id,
                            round=round_number,
                            agent_id=target_id,
                            finding_id=resolution.finding_id,
                            status=resolution.status,
                            trace_id=str(uuid4()),
                        )
                    )

            # Re-synthesize with the revised outputs, then re-review.
            coordinator.engine.transition(MultiAgentWorkflowState.SYNTHESIZING, "revision complete")
            runtime_handoffs.extend(
                _validate_stage_inputs(
                    plan.tasks,
                    plan.stages[2],
                    registry,
                    prior_outputs,
                    requirement,
                    sender_stage_overrides=revision_stage_by_agent,
                )
            )
            _run_and_accumulate(
                stages,
                scheduler,
                plan.stages[2],
                next_stage,
                executors,
                base_context,
                prior_outputs,
                plan.tasks,
                registry,
                schema_registry,
                guard,
            )
            next_stage += 1
            coordinator.engine.transition(MultiAgentWorkflowState.RE_REVIEWING, "re-review")
            guard.record_re_review_invocation()
            runtime_handoffs.extend(
                _validate_stage_inputs(
                    plan.tasks,
                    plan.stages[3],
                    registry,
                    prior_outputs,
                    requirement,
                    sender_stage_overrides={"synthesis-agent-v1": next_stage - 1},
                )
            )
            _run_and_accumulate(
                stages,
                scheduler,
                plan.stages[3],
                next_stage,
                executors,
                base_context,
                prior_outputs,
                plan.tasks,
                registry,
                schema_registry,
                guard,
            )
            next_stage += 1
            revision_events.record(
                RevisionTraceEvent(
                    event_type="REVIEW_RECHECKED",
                    run_id=run_id,
                    round=round_number,
                    agent_id=plan.stages[3][0],
                    status="rechecked",
                    trace_id=str(uuid4()),
                )
            )
            decision = _review_decision(prior_outputs, plan.stages[3][0])
            review_payload = record_review(plan.stages[3][0], round_number)
            _validate_review_findings(review_payload, plan=plan, evidence_summary=evidence_summary)
            if decision == "REJECT" and controller.exhausted:
                terminal_state = "needs_human_review"
                break

        if terminal_state == "needs_human_review":
            coordinator.engine.transition(
                MultiAgentWorkflowState.NEEDS_HUMAN_REVIEW,
                "revision limit reached with rejection",
            )
            revision_events.record(
                RevisionTraceEvent(
                    event_type="HUMAN_REVIEW_REQUIRED",
                    run_id=run_id,
                    round=controller.current_round,
                    agent_id=plan.stages[3][0],
                    status="needs_human_review",
                    trace_id=str(uuid4()),
                )
            )
        else:
            coordinator.engine.transition(MultiAgentWorkflowState.COMPLETED, "review passed")
        revision_exhausted = terminal_state == "needs_human_review"
    except Exception:
        logger.exception(
            "run %s failed with an unexpected error in phase %s",
            run_id,
            coordinator.engine.state.value,
        )
        _persist_failed_run(
            output=output,
            run_id=run_id,
            coordinator=coordinator,
            registry=registry,
            model=model,
            stages=stages,
            plan=plan,
            discovered_files=discovered_files,
            guard=guard,
            error="MULTI_AGENT_RUN_FAILED",
            task_brief_artifact=task_brief_artifact,
            task_brief_events=task_brief_events.snapshot(),
            revision_events=revision_events.snapshot(),
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
    traces = _build_trace_tree(
        stages,
        registry,
        run_id,
        model,
        coordinator.engine.state.value,
        task_brief_events.snapshot(),
        revision_events.snapshot(),
        guard.model_call_events(),
    )
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
        "terminal_state": coordinator.engine.state.value,
        "review": {
            "decision": decision,
            "review_count": len(review_records),
            "finding_count": sum(len(record.get("findings", [])) for record in review_records),
            "finding_ids": sorted(
                {
                    finding["finding_id"]
                    for record in review_records
                    for finding in record.get("findings", [])
                }
            ),
        },
        "revision": {
            "task_count": len(controller.tasks),
            "revision_rounds": controller.current_round,
            "target_agents": sorted(revision_stage_by_agent),
            "unresolved_finding_count": sum(
                len(result.unresolved_finding_ids) for result in revision_results
            ),
            "final_review_decision": decision,
        },
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
            "task_briefs": "task-briefs.json",
            "review_findings": "review-findings.json",
            "revision_tasks": "revision-tasks.json",
            "revision_inputs": "revision-inputs.json",
            "revision_results": "revision-results.json",
            "finding_resolutions": "finding-resolutions.json",
        },
        "task_briefs": {
            "schema_version": task_brief_artifact.schema_version,
            "canonical_hash": task_brief_artifact.canonical_hash,
            "generated_count": task_brief_artifact.generated_count,
            "enriched_agents": list(task_brief_artifact.enriched_agents),
            "degraded_agents": list(task_brief_artifact.degraded_agents),
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
        "budget_snapshot": guard.snapshot(),
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
    try:
        _safe_write(run_dir, "checkpoints.json", checkpoints, guard)
        _safe_write(
            run_dir,
            "task-briefs.json",
            task_brief_artifact.model_dump(mode="json"),
            guard,
            sort_keys=True,
        )
        _safe_write(run_dir, "review-findings.json", review_records, guard, sort_keys=True)
        _safe_write(
            run_dir,
            "revision-tasks.json",
            [task.as_dict() for task in controller.tasks],
            guard,
            sort_keys=True,
        )
        _safe_write(
            run_dir,
            "revision-inputs.json",
            [revision_input.model_dump(mode="json") for revision_input in revision_inputs],
            guard,
            sort_keys=True,
        )
        _safe_write(
            run_dir,
            "revision-results.json",
            [revision_result.model_dump(mode="json") for revision_result in revision_results],
            guard,
            sort_keys=True,
        )
        _safe_write(
            run_dir,
            "finding-resolutions.json",
            [
                resolution.model_dump(mode="json")
                for revision_result in revision_results
                for resolution in revision_result.resolutions
            ],
            guard,
            sort_keys=True,
        )
        revision_artifact_names = (
            "review-findings.json",
            "revision-tasks.json",
            "revision-inputs.json",
            "revision-results.json",
            "finding-resolutions.json",
        )
        manifest["revision_artifacts"] = {
            name: sha256((run_dir / name).read_bytes()).hexdigest()
            for name in revision_artifact_names
        }
        _safe_write(run_dir, "manifest.json", manifest, guard)
        _safe_write(run_dir, "agent-outputs.json", agent_outputs, guard, sort_keys=True)
        _safe_write(run_dir, "handoffs.json", [handoff.__dict__ for handoff in handoffs], guard)
        _safe_write(run_dir, "traces.json", traces, guard)
        _safe_write(
            run_dir,
            "sources.json",
            {"evidence": evidence_text, "tool_calls": tool_call_records},
            guard,
        )
    except SpecFlowError:
        return 3
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
        guard=guard,
    )
    try:
        _safe_write(run_dir, "metrics.json", metrics.as_dict(), guard)
    except SpecFlowError:
        return 3
    return 5 if terminal_state == "needs_human_review" else 0


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
    tasks: tuple[AgentTask, ...],
    registry: AgentRegistry,
    schema_registry: object,
    guard: RuntimeGuard,
) -> None:
    guard.check_wall_time()
    guard.check_parallel_agents(len(agent_ids))
    for agent_id in agent_ids:
        guard.schedule_agent_invocation()
    validated_inputs = _validated_inputs(
        agent_ids,
        stage_index,
        tasks,
        registry,
        schema_registry,
        context,
        prior_outputs,
    )
    guarded_executors = {
        agent_id: _budgeted_executor(
            _maybe_wrap_mock_revision_executor(executors[agent_id], validated_inputs[agent_id]),
            validated_inputs[agent_id],
            guard,
        )
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
    executor: AgentExecutor, validated_input: AgentExecutionInput, guard: RuntimeGuard
) -> AgentExecutor:
    def run(context: dict[str, Any]) -> dict[str, Any]:
        import time as _time

        guard.start_agent_invocation()
        started = _time.perf_counter()
        try:
            result = executor({**context, "validated_input": validated_input})
            guard.complete_agent_invocation()
            guard.record_agent_latency(max(0, int((_time.perf_counter() - started) * 1000)))
            return result
        except Exception:
            guard.complete_agent_invocation(failed=True)
            guard.record_agent_latency(max(0, int((_time.perf_counter() - started) * 1000)))
            raise

    return run


def _validated_inputs(
    agent_ids: tuple[str, ...],
    stage_index: int,
    tasks: tuple[AgentTask, ...],
    registry: AgentRegistry,
    schema_registry: object,
    context: Mapping[str, Any],
    prior_outputs: Mapping[str, dict[str, Any]],
) -> dict[str, AgentExecutionInput]:
    """Build and validate only the declared input contract for each receiver."""
    output = {agent_id: result.get("output", {}) for agent_id, result in prior_outputs.items()}
    requirement = str(context.get("requirement", ""))
    raw_evidence_summary = context.get("evidence_summary")
    evidence_summary = (
        raw_evidence_summary
        if isinstance(raw_evidence_summary, ControlledEvidenceSummary)
        else ControlledEvidenceSummary.model_validate(raw_evidence_summary)
    )
    run_id = str(context.get("run_id", ""))
    task_by_id = {task.agent_id: task for task in tasks}
    revision_context = context.get("revision_context")
    inputs: dict[str, AgentExecutionInput] = {}
    for agent_id in agent_ids:
        try:
            task = task_by_id[agent_id]
        except KeyError as exc:
            raise ValueError("TASK_BRIEF_MISSING") from exc
        identity = registry.get(agent_id).identity
        role = identity.role.value
        if role == "repository_analyst":
            payload = {
                "requirement": requirement,
                "repository_evidence": evidence_summary.content,
            }
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
        model = schema_registry.get(identity.input_schema_id)
        role_payload = model.model_validate(payload).model_dump()
        missing_dependencies = task.depends_on - output.keys()
        if missing_dependencies:
            raise ValueError("PRIOR_OUTPUT_MISSING")
        dependency_outputs = {
            dependency_id: output[dependency_id] for dependency_id in sorted(task.depends_on)
        }
        inputs[agent_id] = AgentExecutionInput(
            run_id=run_id,
            stage=stage_index,
            agent_id=agent_id,
            role=identity.role,
            requirement=requirement,
            evidence_summary=evidence_summary,
            repository_analysis=role_payload.get("repository_analysis"),
            task_brief=task.task_brief,
            prior_outputs=dependency_outputs,
            revision_context=revision_context,
            output_schema_id=identity.output_schema_id,
        )
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


def _review_payload(outputs: Mapping[str, dict[str, Any]], review_id: str) -> ReviewPayload:
    """Return the schema-validated review payload (structured findings)."""
    output = outputs.get(review_id, {}).get("output", {})
    if not isinstance(output, dict):
        raise ValueError("Review agent output must be a dict")
    return ReviewPayload.model_validate(output)


def _revision_targets(payload: ReviewPayload, plan: EffectiveDelegationPlan) -> tuple[str, ...]:
    """Return revision targets in deterministic topology order.

    Targets are sorted by their original plan stage, then by agent_id, so
    multi-target rounds are reproducible and auditable.
    """
    stage_by_agent = {task.agent_id: task.stage for task in plan.tasks}
    targets = sorted(
        {finding.target_agent_id for finding in payload.findings},
        key=lambda agent_id: (stage_by_agent.get(agent_id, 99), agent_id),
    )
    return tuple(targets)


KNOWN_REVIEW_ARTIFACTS = frozenset(
    {
        "agent-outputs.json",
        "checkpoints.json",
        "finding-resolutions.json",
        "handoffs.json",
        "manifest.json",
        "metrics.json",
        "review-findings.json",
        "revision-inputs.json",
        "revision-results.json",
        "revision-tasks.json",
        "sources.json",
        "task-briefs.json",
        "traces.json",
    }
)


def _validate_review_findings(
    payload: ReviewPayload,
    *,
    plan: EffectiveDelegationPlan,
    evidence_summary: ControlledEvidenceSummary,
) -> None:
    """Fail closed on unknown targets, evidence refs, or artifacts in findings."""
    known_agents = {task.agent_id for task in plan.tasks}
    known_evidence = evidence_summary.reference_ids
    for finding in payload.findings:
        if finding.target_agent_id not in known_agents:
            raise ValueError(
                f"Finding {finding.finding_id} targets unknown agent {finding.target_agent_id}"
            )
        unknown_evidence = set(finding.evidence_refs) - known_evidence
        if unknown_evidence:
            raise ValueError(
                f"Finding {finding.finding_id} references unknown evidence: "
                f"{sorted(unknown_evidence)!r}"
            )
        if (
            finding.affected_artifact is not None
            and finding.affected_artifact not in KNOWN_REVIEW_ARTIFACTS
        ):
            raise ValueError(
                f"Finding {finding.finding_id} references unknown artifact "
                f"{finding.affected_artifact}"
            )


def _parse_revision_result(
    prior_outputs: Mapping[str, dict[str, Any]],
    target_id: str,
    revision_input: RevisionInput,
) -> RevisionResult:
    """Extract and validate the revision envelope produced by the target agent."""
    envelope = prior_outputs.get(target_id, {})
    raw_result = envelope.get("revision_result")
    if not isinstance(raw_result, dict):
        raise ValueError(f"Revision execution for {target_id} did not return a revision_result")
    result = RevisionResult.model_validate(raw_result)
    if result.revision_id != revision_input.revision_id:
        raise ValueError("Revision result revision_id does not match the scheduled task")
    if result.parent_output_hash != revision_input.prior_output_hash:
        raise ValueError("Revision result parent output hash does not match the input")
    return result


def _maybe_wrap_mock_revision_executor(
    executor: AgentExecutor,
    validated_input: AgentExecutionInput,
) -> AgentExecutor:
    """Wrap non-``AgentRunner`` executors during revision stages.

    Real ``AgentRunner`` executors already produce a validated
    ``revision_result``.  Mock/override executors need a deterministic
    revision envelope so mock runs stay complete and auditable.
    """
    from specflow.agents.adapter import AgentRunner

    if validated_input.revision_context is None:
        return executor
    if isinstance(getattr(executor, "__self__", None), AgentRunner):
        return executor
    return _mock_revision_executor(executor, validated_input)


def _mock_revision_executor(
    executor: AgentExecutor,
    validated_input: AgentExecutionInput,
) -> AgentExecutor:
    """Wrap a plain executor with a deterministic, honest revision envelope."""
    from specflow.revision.models import ResolutionStatus

    def run(context: dict[str, Any]) -> dict[str, Any]:
        result = executor({**context, "validated_input": validated_input})
        if isinstance(result.get("revision_result"), dict):
            return result
        revision_context = validated_input.revision_context
        assert revision_context is not None
        output = result.get("output")
        if not isinstance(output, dict):
            return result
        resolutions = tuple(
            FindingResolution(
                finding_id=finding.finding_id,
                status=ResolutionStatus.UNRESOLVED,
                explanation=(
                    "Deterministic mock revision did not change the output; "
                    "the finding remains unresolved."
                ),
            )
            for finding in revision_context.findings
        )
        result["revision_result"] = RevisionResult.build(
            revision_id=revision_context.revision_id,
            revision_round=revision_context.revision_round,
            parent_output_hash=revision_context.prior_output_hash,
            revised_output=ValidatedAgentOutput(
                agent_id=validated_input.agent_id,
                schema_id=validated_input.output_schema_id,
                payload=output,
            ),
            input_finding_ids=tuple(finding.finding_id for finding in revision_context.findings),
            resolutions=resolutions,
        ).model_dump(mode="json")
        return result

    return run


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
    stages,
    registry,
    run_id: str,
    model: str,
    status: str,
    task_brief_events: tuple[TaskBriefTraceEvent, ...] = (),
    revision_events: tuple[RevisionTraceEvent, ...] = (),
    model_call_events: tuple[dict[str, object], ...] = (),
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
    traces.extend(event.as_dict() for event in task_brief_events)
    traces.extend(event.as_dict() for event in revision_events)
    traces.extend(dict(event) for event in model_call_events)
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
    guard.record_artifact_bytes(len(content.encode("utf-8")))
    (run_dir / filename).write_text(content, encoding="utf-8")


def _persist_planning_failure(
    output: Path,
    run_id: str,
    guard: RuntimeGuard,
    error: str,
) -> None:
    """Persist a minimal FAILED manifest with a budget snapshot when planning fails."""
    try:
        run_dir = output / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        failed_manifest = {
            "run_id": run_id,
            "plan_id": "unknown",
            "workflow_state": "failed",
            "workflow_history": [],
            "error": error,
            "failure_stage": "planning",
            "stages_completed": 0,
            "budget_snapshot": guard.last_budget_snapshot or guard.snapshot(),
            "artifacts": {},
        }
        _safe_write(run_dir, "manifest.json", failed_manifest, guard)
        _safe_write(run_dir, "traces.json", list(guard.model_call_events()), guard)
    except Exception:
        logger.debug("Failed to persist planning-failure artifacts", exc_info=True)


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
    guard: RuntimeGuard,
    error: str,
    task_brief_artifact: TaskBriefArtifact,
    task_brief_events: tuple[TaskBriefTraceEvent, ...],
    revision_events: tuple[RevisionTraceEvent, ...] = (),
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
        traces = _build_trace_tree(
            stages,
            registry,
            run_id,
            model,
            "failed",
            task_brief_events,
            revision_events,
            guard.model_call_events(),
        )
        failed_manifest = {
            "run_id": run_id,
            "plan_id": getattr(plan, "plan_id", "unknown"),
            "workflow_state": "failed",
            "workflow_history": list(coordinator.engine.history),
            "error": error,
            "stages_completed": len(stages),
            "discovered_files": discovered_files,
            "failure_code": error,
            "budget_snapshot": guard.last_budget_snapshot or guard.snapshot(),
            "artifacts": {"task_briefs": "task-briefs.json"},
            "task_briefs": {
                "schema_version": task_brief_artifact.schema_version,
                "canonical_hash": task_brief_artifact.canonical_hash,
                "generated_count": task_brief_artifact.generated_count,
                "enriched_agents": list(task_brief_artifact.enriched_agents),
                "degraded_agents": list(task_brief_artifact.degraded_agents),
            },
        }
        _safe_write(
            run_dir,
            "task-briefs.json",
            task_brief_artifact.model_dump(mode="json"),
            guard,
            sort_keys=True,
        )
        _safe_write(run_dir, "manifest.json", failed_manifest, guard)
        _safe_write(run_dir, "traces.json", traces, guard)
        # Persist partial agent outputs for debugging
        agent_outputs = {
            f"stage-{s.stage_index}/{aid}": result
            for s in stages
            for aid, result in s.agent_results.items()
        }
        _safe_write(run_dir, "agent-outputs.json", agent_outputs, guard, sort_keys=True)
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
    guard: RuntimeGuard,
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
            tokens_in = usage.get("input_tokens") or 0
            tokens_out = usage.get("output_tokens") or 0
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

    snapshot = guard.snapshot()
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
        configured_role_count=int(snapshot["configured_role_count"]),
        agent_invocations_scheduled=int(snapshot["agent_invocations"]["scheduled"]),
        agent_invocations_completed=int(snapshot["agent_invocations"]["completed"]),
        agent_invocations_failed=int(snapshot["agent_invocations"]["failed"]),
        provider_call_attempts=int(snapshot["provider_calls"]["attempts"]),
        successful_provider_calls=int(snapshot["provider_calls"]["successful"]),
        failed_provider_calls=int(snapshot["provider_calls"]["failed"]),
        peak_active_provider_calls=int(snapshot["provider_calls"]["peak_active"]),
        synthetic_model_calls=int(snapshot["synthetic_model_calls"]),
        token_usage_known=bool(snapshot["tokens"]["usage_known"]),
        token_usage_unknown_calls=int(snapshot["tokens"]["unknown_calls"]),
        revision_agent_invocations=int(snapshot["revision"]["agent_invocations"]),
        re_review_invocations=int(snapshot["revision"]["re_review_invocations"]),
        provider_latency_ms=int(snapshot["timing"]["provider_latency_ms"]),
        budget_snapshot=snapshot,
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
