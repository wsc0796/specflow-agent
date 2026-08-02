"""Tests for multi-agent runner and CLI --mode multi-agent."""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from task_brief_test_helpers import controlled_evidence, task_brief

from specflow.plan.hash_utils import canonical_json_bytes
from specflow.plan.models import AgentTask, TaskBriefArtifact
from specflow.plan.planner import DeterministicPlanner
from specflow.policy.models import ExecutionPolicy
from specflow.runner_multi import _build_registry, _validated_inputs, run_multi_agent
from specflow.schema import build_schema_registry


class ScriptedExecutionClient:
    """Exercises enrichment and all real AgentRunner requests without network I/O."""

    def __init__(self, *, fail_enrichment_for: str = "") -> None:
        self.requests = []
        self.fail_enrichment_for = fail_enrichment_for

    def complete(self, request):
        self.requests.append(request)
        message = request.messages[-1].content
        if "[Task Brief Enrichment Input]" in message:
            if self.fail_enrichment_for and self.fail_enrichment_for in message:
                raise TimeoutError("sensitive provider timeout detail")
            agent_id = next(
                candidate
                for candidate in (
                    "repository-analyst-agent-v1",
                    "design-agent-v1",
                    "test-strategy-agent-v1",
                    "risk-review-agent-v1",
                    "synthesis-agent-v1",
                    "review-agent-v1",
                )
                if candidate in message
            )
            payload = {
                "task_description": f"ROLE_BRIEF_SECRET_MARKER:{agent_id}",
                "analysis_focus": ["role boundary"],
                "evaluation_hints": ["preserve evidence"],
                "repository_scope_hint": "src/",
                "evidence_refs": [],
            }
        elif "agent/repository-analyst/v1/output" in message:
            payload = {"summary": "repository analysis"}
        elif "agent/design/v1/output" in message:
            payload = {"summary": "design"}
        elif "agent/test-strategy/v1/output" in message:
            payload = {"summary": "tests"}
        elif "agent/risk-review/v1/output" in message:
            payload = {"summary": "risks"}
        elif "agent/synthesis/v1/output" in message:
            payload = {"summary": "synthesis"}
        elif "agent/review/v1/output" in message:
            payload = {"decision": "PASS", "summary": "review"}
        else:
            raise AssertionError("Unexpected LLM request")

        class Response:
            content = json.dumps(payload)
            input_tokens = 10
            output_tokens = 5

        return Response()


class FailingFirstWorkerClient(ScriptedExecutionClient):
    """Succeeds during six enrichments, then fails the first worker request."""

    def complete(self, request):
        if len(self.requests) >= 6:
            self.requests.append(request)
            raise RuntimeError("worker failure probe")
        return super().complete(request)


class TestMultiAgentRunner:
    def test_receiver_input_schema_is_executed_before_scheduling(self) -> None:
        registry = _build_registry()
        schemas = build_schema_registry()
        spec = DeterministicPlanner().generate()
        identity = next(agent for agent in spec.agents if agent.agent_id == "design-agent-v1")
        dependency = next(item for item in spec.dependencies if item.agent_id == identity.agent_id)
        constraints = next(item for item in spec.constraints if item.agent_id == identity.agent_id)
        task = AgentTask(
            agent_id=identity.agent_id,
            role=identity.role,
            stage=1,
            depends_on=dependency.depends_on,
            constraints=constraints,
            task_brief=task_brief(
                agent_id=identity.agent_id,
                role=identity.role,
                output_schema_id=identity.output_schema_id,
            ),
        )
        with pytest.raises(Exception, match="valid dictionary"):
            _validated_inputs(
                ("design-agent-v1",),
                1,
                (task,),
                registry,
                schemas,
                {
                    "run_id": "run-test",
                    "requirement": "Test",
                    "evidence_summary": controlled_evidence(),
                },
                {"repository-analyst-agent-v1": {"output": "not-a-dict"}},
            )

    def test_run_multi_agent_mock_mode(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo")
        output = tmp_path / "output"
        exit_code = run_multi_agent(
            repo=repo, requirement="Add feature X", output=output, mock=True
        )
        assert exit_code == 0
        assert len(list(output.glob("run-multi-*"))) == 1

    def test_provider_mock_is_accounted_as_synthetic_without_mock_flag(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo")
        output = tmp_path / "output"

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Inspect repository",
                output=output,
                provider="mock",
                mock=False,
            )
            == 0
        )
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        snapshot = manifest["budget_snapshot"]
        assert snapshot["execution_mode"] == "mock"
        assert snapshot["provider_calls"]["attempts"] == 0
        assert snapshot["synthetic_model_calls"] == 6

    def test_failed_manifest_uses_terminal_agent_snapshot(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo")
        output = tmp_path / "output"

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Inspect repository",
                output=output,
                provider="openai-compatible",
                model="test-model",
                _llm_client_override=FailingFirstWorkerClient(),
            )
            == 3
        )
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        invocations = manifest["budget_snapshot"]["agent_invocations"]
        assert invocations == {
            "scheduled": 1,
            "started": 1,
            "completed": 0,
            "failed": 1,
            "active": 0,
        }
        assert manifest["triggering_budget_snapshot"]["provider_calls"]["failed"] == 1

    def test_manifest_contains_three_hashes(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test")
        output = tmp_path / "output"
        run_multi_agent(repo=repo, requirement="Test", output=output, mock=True)
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        assert len(manifest["structure_hash"]) == 64
        assert len(manifest["semantic_brief_hash"]) == 64
        assert len(manifest["effective_plan_hash"]) == 64
        assert manifest["enriched"] is True

    def test_mock_run_persists_outputs_handoffs_and_traces(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test")
        output = tmp_path / "output"

        assert run_multi_agent(repo=repo, requirement="Test", output=output, mock=True) == 0

        run_dir = next(output.glob("run-multi-*"))
        outputs = json.loads((run_dir / "agent-outputs.json").read_text())
        handoffs = json.loads((run_dir / "handoffs.json").read_text())
        traces = json.loads((run_dir / "traces.json").read_text())
        assert len(outputs) == 6
        assert len(handoffs) == 7
        # 8 spans + 6 brief GENERATED + 1 REVIEW_FINDINGS_CREATED
        # + 6 synthetic MODEL_CALL_SUCCEEDED (mock enrichment is not a provider call)
        assert len(traces) == 21
        root = next(trace for trace in traces if trace.get("kind") == "run")
        coordinator = next(trace for trace in traces if trace.get("kind") == "coordinator")
        agent_traces = [trace for trace in traces if "agent_version" in trace]
        generated = [trace for trace in traces if trace.get("event_type") == "TASK_BRIEF_GENERATED"]
        consumed = [trace for trace in traces if trace.get("event_type") == "TASK_BRIEF_CONSUMED"]
        review_events = [
            trace for trace in traces if trace.get("event_type") == "REVIEW_FINDINGS_CREATED"
        ]
        synthetic_events = [
            trace
            for trace in traces
            if trace.get("event_type") == "MODEL_CALL_SUCCEEDED" and trace.get("synthetic")
        ]
        assert root["parent_span_id"] is None
        assert coordinator["parent_span_id"] == root["span_id"]
        assert len(agent_traces) == 6
        assert len(generated) == 6
        assert consumed == []
        assert len(review_events) == 1
        assert review_events[0]["status"] == "PASS"
        assert len(synthetic_events) == 6
        assert {trace["parent_span_id"] for trace in agent_traces} == {coordinator["span_id"]}

        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["schema_validated_count"] == 6
        assert metrics["schema_unvalidated_count"] == 0
        assert metrics["fallback_count"] == 0
        assert metrics["review_decision"] == "PASS"

    def test_mock_artifacts_use_schema_validated_sanitized_outputs(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "orders.py").write_text("# order timeout cancellation state")
        output = tmp_path / "output"

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Cancel timed out orders without duplicate transitions",
                output=output,
                mock=True,
            )
            == 0
        )

        run_dir = next(output.glob("run-multi-*"))
        outputs = json.loads((run_dir / "agent-outputs.json").read_text(encoding="utf-8"))
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
        serialized_artifacts = "\n".join(
            artifact.read_text(encoding="utf-8")
            for artifact in run_dir.iterdir()
            if artifact.is_file()
        )

        assert len(outputs) == 6
        assert all(result["schema_validated"] is True for result in outputs.values())
        assert metrics["selected_file_count"] > 0
        assert metrics["referenced_file_count"] > 0
        assert str(repo.resolve()) not in serialized_artifacts
        assert "api_key=secret" not in serialized_artifacts

    def test_real_agent_requests_persist_consumed_events_and_task_brief_artifact(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "app.py").write_text("# searchable repository evidence")
        output = tmp_path / "output"
        client = ScriptedExecutionClient()
        policy = ExecutionPolicy(max_provider_call_attempts=100)

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Inspect searchable repository evidence",
                output=output,
                provider="openai-compatible",
                _llm_client_override=client,
                policy=policy,
            )
            == 0
        )

        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        artifact_data = json.loads(
            (run_dir / manifest["artifacts"]["task_briefs"]).read_text(encoding="utf-8")
        )
        artifact = TaskBriefArtifact.model_validate(artifact_data)
        traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
        generated = [event for event in traces if event.get("event_type") == "TASK_BRIEF_GENERATED"]
        consumed = [event for event in traces if event.get("event_type") == "TASK_BRIEF_CONSUMED"]
        worker_requests = [
            request
            for request in client.requests
            if "[Original Requirement]" in request.messages[-1].content
        ]

        assert len(worker_requests) == 6
        assert all(
            all(
                f"[{section}]" in request.messages[-1].content
                for section in (
                    "Original Requirement",
                    "Verified Repository Evidence",
                    "Role Task Brief",
                    "Validated Prior Stage Outputs",
                    "Role-specific Output Contract",
                )
            )
            for request in worker_requests
        )
        for agent_id in artifact.brief_hashes:
            own_request = next(
                request.messages[-1].content
                for request in worker_requests
                if f"ROLE_BRIEF_SECRET_MARKER:{agent_id}" in request.messages[-1].content
            )
            assert all(
                f"ROLE_BRIEF_SECRET_MARKER:{other_id}" not in own_request
                for other_id in artifact.brief_hashes
                if other_id != agent_id
            )
        assert len(generated) == 6
        assert len(consumed) == 6
        assert {event["agent_id"] for event in consumed} == set(artifact.brief_hashes)
        assert manifest["task_briefs"]["canonical_hash"] == artifact.canonical_hash
        assert manifest["task_briefs"]["generated_count"] == 6
        assert "ROLE_BRIEF_SECRET_MARKER" not in json.dumps(traces)

    def test_degraded_enrichment_is_audited_and_still_reaches_real_request(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        output = tmp_path / "output"
        client = ScriptedExecutionClient(fail_enrichment_for="design-agent-v1")
        policy = ExecutionPolicy(max_provider_call_attempts=100)

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Inspect design",
                output=output,
                provider="openai-compatible",
                _llm_client_override=client,
                policy=policy,
            )
            == 0
        )
        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
        design_consumed = next(
            event
            for event in traces
            if event.get("event_type") == "TASK_BRIEF_CONSUMED"
            and event["agent_id"] == "design-agent-v1"
        )
        design_request = next(
            request.messages[-1].content
            for request in client.requests
            if "agent/design/v1/output" in request.messages[-1].content
            and "[Original Requirement]" in request.messages[-1].content
        )
        assert manifest["task_briefs"]["degraded_agents"] == ["design-agent-v1"]
        assert design_consumed["status"] == "degraded"
        assert '"status": "degraded"' in design_request
        assert "sensitive provider timeout detail" not in json.dumps(traces)

    def test_reject_after_revision_limit_enters_needs_human_review(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        output = tmp_path / "output"
        reviews = 0
        finding = {
            "schema_version": "review_finding/v1",
            "finding_id": "F-00000001",
            "severity": "warning",
            "category": "completeness",
            "description": "Design omits persistence module coverage.",
            "target_agent_id": "design-agent-v1",
            "affected_artifact": None,
            "evidence_refs": [],
            "recommendation": "Add persistence module coverage to the design.",
        }

        def reject_review(_: dict[str, object]) -> dict[str, object]:
            nonlocal reviews
            reviews += 1
            return {
                "agent_id": "review-agent-v1",
                "role": "review",
                "output": {
                    "decision": "REJECT",
                    "summary": "Explicit mock rejection for revision coverage.",
                    "requires_revision": True,
                    "findings": [finding],
                },
            }

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test revision",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": reject_review},
            )
            == 5
        )
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        assert reviews == 2
        assert manifest["workflow_state"] == "needs_human_review"
        assert manifest["terminal_state"] == "needs_human_review"
        assert manifest["revision_count"] == 1
        assert manifest["revision_exhausted"] is True
        assert manifest["review"]["decision"] == "REJECT"
        assert manifest["review"]["finding_count"] == 2
        assert manifest["revision"]["task_count"] == 1
        assert manifest["revision"]["unresolved_finding_count"] == 1
        assert [step[1] for step in manifest["workflow_history"]].count("revising") == 1
        assert "needs_human_review" in [step[1] for step in manifest["workflow_history"]]
        run_dir = next(output.glob("run-multi-*"))
        outputs = json.loads((run_dir / "agent-outputs.json").read_text(encoding="utf-8"))
        assert "stage-1/design-agent-v1" in outputs
        assert "stage-4/design-agent-v1" in outputs
        traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
        event_types = [trace["event_type"] for trace in traces if "event_type" in trace]
        assert event_types.count("REVIEW_FINDINGS_CREATED") == 2
        assert event_types.count("REVISION_REQUEST_SUBMITTED") == 0  # mock path, honest
        assert event_types.count("FINDING_UNRESOLVED") == 1
        assert event_types.count("HUMAN_REVIEW_REQUIRED") == 1
        revision_tasks = json.loads((run_dir / "revision-tasks.json").read_text(encoding="utf-8"))
        assert revision_tasks[0]["finding_ids"] == ["F-00000001"]
        assert revision_tasks[0]["status"] == "completed"
        revision_inputs = json.loads((run_dir / "revision-inputs.json").read_text(encoding="utf-8"))
        assert revision_inputs[0]["revision_round"] == 1
        assert revision_inputs[0]["target_agent_id"] == "design-agent-v1"
        resolutions = json.loads((run_dir / "finding-resolutions.json").read_text(encoding="utf-8"))
        assert resolutions[0]["finding_id"] == "F-00000001"
        assert resolutions[0]["status"] == "unresolved"
        handoffs = json.loads((run_dir / "handoffs.json").read_text(encoding="utf-8"))
        assert any(
            handoff["payload_ref"].endswith("stage-1/design-agent-v1") for handoff in handoffs
        )
        assert any(handoff["handoff_id"].startswith("handoff-revision-") for handoff in handoffs)
        for handoff in handoffs:
            payload_key = handoff["payload_ref"].removeprefix("agent-outputs.json#")
            assert (
                handoff["output_hash"]
                == sha256(canonical_json_bytes(outputs[payload_key])).hexdigest()
            )

    def test_non_mock_provider_is_rejected_without_executing_agents(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        called = False

        def should_not_run(_: dict[str, object]) -> dict[str, object]:
            nonlocal called
            called = True
            return {}

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=tmp_path / "output",
                provider="openai-compatible",
                _executor_overrides={"review-agent-v1": should_not_run},
            )
            == 2
        )
        assert called is False

    def test_duplicate_run_is_rejected_before_executors_run(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        output = tmp_path / "output"
        assert run_multi_agent(repo=repo, requirement="Test", output=output, mock=True) == 0
        called = False

        def should_not_run(_: dict[str, object]) -> dict[str, object]:
            nonlocal called
            called = True
            return {}

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": should_not_run},
            )
            == 3
        )
        assert called is False

    def test_required_agent_failure_stops_before_specialists(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        specialists_called = False

        def required_failure(_: dict[str, object]) -> dict[str, object]:
            return {
                "agent_id": "repository-analyst-agent-v1",
                "role": "repository_analyst",
                "success": False,
                "output": {"degraded": True, "error_code": "SCHEMA_VALIDATION_FAILED"},
            }

        def must_not_run(_: dict[str, object]) -> dict[str, object]:
            nonlocal specialists_called
            specialists_called = True
            return {}

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test required failure",
                output=tmp_path / "output",
                mock=True,
                _executor_overrides={
                    "repository-analyst-agent-v1": required_failure,
                    "design-agent-v1": must_not_run,
                },
            )
            == 3
        )
        assert specialists_called is False

    def test_llm_call_policy_stops_run_before_unbounded_execution(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        policy = ExecutionPolicy(max_provider_call_attempts=1)

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Policy budget",
                output=tmp_path / "output",
                provider="openai-compatible",
                _llm_client_override=ScriptedExecutionClient(),
                policy=policy,
            )
            == 3
        )
        manifest = json.loads(
            (next((tmp_path / "output").glob("run-multi-*")) / "manifest.json").read_text()
        )
        assert manifest["workflow_state"] == "failed"

    def test_parallel_policy_stops_stage_before_agents_start(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        output = tmp_path / "output"
        policy = ExecutionPolicy(max_parallel_agents=2)

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Parallel policy",
                output=output,
                mock=True,
                policy=policy,
            )
            == 3
        )
        manifest = json.loads((next(output.glob("run-multi-*")) / "manifest.json").read_text())
        assert manifest["workflow_state"] == "failed"
