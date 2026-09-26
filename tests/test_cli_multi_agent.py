"""Tests for multi-agent runner and CLI --mode multi-agent."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from specflow.handoff.validator import HandoffValidator
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.policy.models import ExecutionPolicy
from specflow.runner_multi import (
    _build_registry,
    _RequestObservingLLMClient,
    _sanitize_artifact_value,
    _validated_inputs,
    run_multi_agent,
)
from specflow.schema import build_schema_registry


def _write_matching_evidence(repo: Path, requirement: str) -> None:
    (repo / "evidence.py").write_text(f"# {requirement}\n", encoding="utf-8")


class TestMultiAgentRunner:
    def test_default_product_evidence_cap_remains_ten(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed_caps = []

        class CapturingCollector:
            tool_call_records = ()

            def __init__(self, *args, config, **kwargs):
                observed_caps.append(config.max_selected_files)

            def collect(self, **kwargs):
                raise RuntimeError("stop after observing the product default")

        monkeypatch.setattr("specflow.runner_multi.EvidenceCollector", CapturingCollector)
        repo = tmp_path / "repo"
        repo.mkdir()

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Observe the default evidence cap",
                output=tmp_path / "output",
                mock=True,
            )
            == 3
        )
        assert observed_caps == [10]

    def test_request_observer_is_non_interfering_and_preserves_provider_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from specflow.llm import LLMMessage, LLMRequest, LLMResponse, LLMUsage
        from specflow.llm.exceptions import LLMResponseError

        request = LLMRequest(
            model="test-model",
            messages=[LLMMessage(role="user", content="hello")],
            response_format="json",
        )
        response = LLMResponse(
            content='{"ok": true}',
            model="test-model",
            usage=LLMUsage(input_tokens=3, output_tokens=2),
            latency_ms=1,
            finish_reason="stop",
        )
        forwarded = []

        class Provider:
            def complete(self, value):
                forwarded.append(value)
                return response

        def broken_observer(_):
            raise RuntimeError("observer failed")

        client = _RequestObservingLLMClient(
            Provider(), receiver="repository-analyst-agent-v1", observer=broken_observer
        )
        assert client.complete(request) is response
        assert forwarded == [request]
        assert "observation" in caplog.text

        original = LLMResponseError("synthetic provider failure")

        class FailingProvider:
            def complete(self, value):
                forwarded.append(value)
                raise original

        seen = []
        client = _RequestObservingLLMClient(
            FailingProvider(), receiver="review-agent-v1", observer=seen.append
        )
        with pytest.raises(LLMResponseError) as failure:
            client.complete(request)
        assert failure.value is original
        assert forwarded[-1] is request
        assert len(seen) == 1
        assert seen[0].receiver == "review-agent-v1"
        assert seen[0].messages == (("user", "hello"),)

    def test_live_branch_observes_enrichment_and_agent_contexts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specflow.llm import LLMResponse, LLMUsage

        class FakeProvider:
            def __init__(self):
                self.requests = []

            def complete(self, request):
                self.requests.append(request)
                system = request.messages[0].content if request.messages[0].role == "system" else ""
                if not system:
                    content = json.dumps(
                        {
                            "task_description": "Use the declared receiver input only.",
                            "analysis_focus": [],
                            "evaluation_hints": [],
                            "repository_scope_hint": "",
                        }
                    )
                elif "repository_analyst" in system:
                    content = json.dumps(
                        {
                            "summary": "Repository evidence reviewed.",
                            "affected_components": [],
                            "key_files": [],
                            "technology_notes": "",
                            "evidence_count": 1,
                        }
                    )
                elif "test_strategy" in system:
                    content = json.dumps({"summary": "Test strategy."})
                elif "risk_review" in system:
                    content = json.dumps({"summary": "Risk review."})
                elif "synthesis" in system:
                    content = json.dumps({"summary": "Synthesis."})
                elif "review" in system:
                    content = json.dumps({"decision": "PASS", "summary": "Review passed."})
                else:
                    content = json.dumps({"summary": "Design."})
                return LLMResponse(
                    content=content,
                    model="test-model",
                    usage=LLMUsage(input_tokens=3, output_tokens=2),
                    latency_ms=1,
                    finish_reason="stop",
                )

        provider = FakeProvider()
        monkeypatch.setattr(
            "specflow.runner_multi._create_real_llm_client", lambda *args, **kwargs: provider
        )
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "evidence.py").write_text(
            "# health feature EVIDENCE_ONLY_MARKER\n", encoding="utf-8"
        )
        observations = []

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Explain the health feature",
                output=tmp_path / "output",
                provider="openai-compatible",
                model="test-model",
                policy=ExecutionPolicy(max_llm_calls=12),
                request_observer=observations.append,
            )
            == 0
        )

        assert len(observations) == len(provider.requests) == 12
        enrichments = [item for item in observations if item.receiver == "coordinator_enricher"]
        assert [item.call_index for item in enrichments] == list(range(1, 7))
        agent_observations = [
            item for item in observations if item.receiver != "coordinator_enricher"
        ]
        assert {item.receiver for item in agent_observations} == {
            "repository-analyst-agent-v1",
            "design-agent-v1",
            "test-strategy-agent-v1",
            "risk-review-agent-v1",
            "synthesis-agent-v1",
            "review-agent-v1",
        }
        repository_request = next(
            item for item in agent_observations if item.receiver == "repository-analyst-agent-v1"
        )
        assert "EVIDENCE_ONLY_MARKER" in str(repository_request.messages)
        assert all(
            "EVIDENCE_ONLY_MARKER" not in str(item.messages)
            for item in agent_observations
            if item.receiver != "repository-analyst-agent-v1"
        )

    def test_artifact_sanitization_uses_full_dlp_ruleset(self) -> None:
        raw_values = {
            "openai": "sk-" + "abc123def456ghi789jkl012mno345pqr678stu",
            "github": "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz",
            "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature",
            "assignment": 'client_secret = "artifact-' + 'secret"',
            "path": "C:/sensitive/repository/config.py",
        }

        sanitized = _sanitize_artifact_value(raw_values)
        serialized = json.dumps(sanitized)

        for secret in (
            "sk-" + "abc123def456ghi789jkl012mno345pqr678stu",
            "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz",
            "eyJhbGciOiJIUzI1NiJ9",
            "artifact-secret",
            "C:/sensitive/repository/config.py",
        ):
            assert secret not in serialized
        assert "sk-<redacted>" in serialized
        assert "ghp_<redacted>" in serialized
        assert "<jwt>" in serialized
        assert "<absolute-path-redacted>" in serialized

    def test_receiver_input_schema_is_executed_before_scheduling(self) -> None:
        registry = _build_registry()
        schemas = build_schema_registry()
        with pytest.raises(Exception, match="valid dictionary"):
            _validated_inputs(
                ("design-agent-v1",),
                registry,
                schemas,
                {"requirement": "Test"},
                {"repository-analyst-agent-v1": {"output": "not-a-dict"}},
            )

    def test_run_multi_agent_mock_mode(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo")
        _write_matching_evidence(repo, "Add feature X")
        output = tmp_path / "output"
        exit_code = run_multi_agent(
            repo=repo, requirement="Add feature X", output=output, mock=True
        )
        assert exit_code == 0
        assert len(list(output.glob("run-multi-*"))) == 1

    def test_zero_evidence_fails_before_agents_and_persists_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "app.py").write_text("def existing_feature():\n    return True\n")
        output = tmp_path / "output"
        repository_analyst_called = False
        coordinator_plan_called = False

        def must_not_plan(*_: object) -> object:
            nonlocal coordinator_plan_called
            coordinator_plan_called = True
            raise AssertionError("Coordinator.plan must not run without repository evidence")

        monkeypatch.setattr("specflow.runner_multi.Coordinator.plan", must_not_plan)

        def must_not_run(_: dict[str, object]) -> dict[str, object]:
            nonlocal repository_analyst_called
            repository_analyst_called = True
            return {
                "agent_id": "repository-analyst-agent-v1",
                "role": "repository_analyst",
                "output": {
                    "summary": "This executor must not run without repository evidence.",
                    "affected_components": [],
                    "key_files": [],
                    "technology_notes": "",
                    "evidence_count": 0,
                },
            }

        exit_code = run_multi_agent(
            repo=repo,
            requirement="totally_missing_symbol_xyz_74219",
            output=output,
            mock=True,
            _executor_overrides={"repository-analyst-agent-v1": must_not_run},
        )

        assert exit_code == 3
        assert repository_analyst_called is False
        assert coordinator_plan_called is False
        run_dir = next(output.glob("run-multi-*"))
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["workflow_state"] == "failed"
        assert manifest["error"] == "EVIDENCE_NOT_FOUND"
        assert manifest["stages_completed"] == 0
        assert manifest["selected_file_count"] == 0
        assert manifest["referenced_file_count"] == 0
        assert str(repo.resolve()) not in json.dumps(manifest)
        integrity = json.loads((run_dir / "artifact-integrity.json").read_text(encoding="utf-8"))
        assert (
            integrity["artifact_hashes"]["manifest.json"]
            == sha256(manifest_path.read_bytes()).hexdigest()
        )
        assert (run_dir / "_COMPLETE").is_file()

    def test_manifest_contains_three_hashes(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test")
        _write_matching_evidence(repo, "Test")
        output = tmp_path / "output"
        run_multi_agent(repo=repo, requirement="Test", output=output, mock=True)
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        assert len(manifest["structure_hash"]) == 64
        assert len(manifest["semantic_brief_hash"]) == 64
        assert len(manifest["effective_plan_hash"]) == 64
        assert manifest["enriched"] is True

    def test_artifacts_are_atomic_and_integrity_marked(self, tmp_path: Path) -> None:
        """Runs must end with a completion marker and per-file SHA-256 hashes."""
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test")
        _write_matching_evidence(repo, "Test")
        output = tmp_path / "output"

        assert run_multi_agent(repo=repo, requirement="Test", output=output, mock=True) == 0

        run_dir = next(output.glob("run-multi-*"))
        assert (run_dir / "_COMPLETE").is_file()
        assert not list(run_dir.glob(".*.tmp"))  # no leftover temp files

        integrity = json.loads((run_dir / "artifact-integrity.json").read_text(encoding="utf-8"))
        assert set(integrity["artifact_hashes"]) >= {
            "manifest.json",
            "metrics.json",
            "agent-outputs.json",
            "handoffs.json",
            "traces.json",
            "sources.json",
        }
        for name, digest in integrity["artifact_hashes"].items():
            assert sha256((run_dir / name).read_bytes()).hexdigest() == digest

    def test_policy_failure_persists_specific_error_code(self, tmp_path: Path) -> None:
        """Budget violations must be recorded with their exact code, not a blanket error."""
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test")
        _write_matching_evidence(repo, "Test")
        output = tmp_path / "output"
        policy = ExecutionPolicy(max_llm_calls=1)

        exit_code = run_multi_agent(
            repo=repo, requirement="Test", output=output, mock=True, policy=policy
        )

        assert exit_code == 3
        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["error"] == "CALL_BUDGET_EXCEEDED"

    def test_mock_run_persists_outputs_handoffs_and_traces(self, tmp_path: Path) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test")
        _write_matching_evidence(repo, "Test")
        output = tmp_path / "output"

        assert run_multi_agent(repo=repo, requirement="Test", output=output, mock=True) == 0

        run_dir = next(output.glob("run-multi-*"))
        outputs = json.loads((run_dir / "agent-outputs.json").read_text())
        handoffs = json.loads((run_dir / "handoffs.json").read_text())
        traces = json.loads((run_dir / "traces.json").read_text())
        assert len(outputs) == 6
        assert len(handoffs) == 7
        assert len(traces) == 8
        root = next(trace for trace in traces if trace.get("kind") == "run")
        coordinator = next(trace for trace in traces if trace.get("kind") == "coordinator")
        agent_traces = [trace for trace in traces if "agent_id" in trace]
        assert root["parent_span_id"] is None
        assert coordinator["parent_span_id"] == root["span_id"]
        assert len(agent_traces) == 6
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

    def test_handoff_integrity_failure_stops_receiver_and_persists_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Post-hash tampering must fail closed with bounded handoff diagnostics."""
        repo = tmp_path / "test-repo"
        repo.mkdir()
        _write_matching_evidence(repo, "Test handoff integrity")
        output = tmp_path / "output"
        receiver_called = False
        tampered_value = "tampered-payload-sentinel"
        original_validate_payload = HandoffValidator.validate_payload

        def validate_tampered_payload(self, handoff, sender, payloads):
            tampered_payloads = deepcopy(payloads)
            payload_key = handoff.payload_ref.removeprefix("agent-outputs.json#")
            tampered_payloads[payload_key]["output"]["summary"] = tampered_value
            return original_validate_payload(self, handoff, sender, tampered_payloads)

        def receiver_must_not_run(_: dict[str, object]) -> dict[str, object]:
            nonlocal receiver_called
            receiver_called = True
            return {}

        monkeypatch.setattr(HandoffValidator, "validate_payload", validate_tampered_payload)

        exit_code = run_multi_agent(
            repo=repo,
            requirement="Test handoff integrity",
            output=output,
            mock=True,
            _executor_overrides={"design-agent-v1": receiver_must_not_run},
        )

        assert exit_code == 3
        assert receiver_called is False
        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
        expected_context = {
            "from_agent_id": "repository-analyst-agent-v1",
            "to_agent_id": "design-agent-v1",
            "payload_ref": "agent-outputs.json#stage-0/repository-analyst-agent-v1",
        }

        assert manifest["workflow_state"] == "failed"
        assert manifest["error"] == "HANDOFF_INTEGRITY_FAILED"
        assert manifest["failure_context"].pop("handoff_id").startswith("handoff-")
        assert manifest["failure_context"] == expected_context
        for trace in traces:
            if trace.get("kind") in {"run", "coordinator"}:
                assert trace["error_code"] == "HANDOFF_INTEGRITY_FAILED"
                assert trace["failure_context"]["handoff_id"].startswith("handoff-")
                assert {
                    key: trace["failure_context"][key] for key in expected_context
                } == expected_context

        serialized_failure = "\n".join(
            path.read_text(encoding="utf-8") for path in run_dir.iterdir() if path.is_file()
        )
        assert tampered_value not in serialized_failure
        assert str(repo.resolve()) not in serialized_failure
        assert "expected_hash" not in serialized_failure
        assert "actual_hash" not in serialized_failure

    def test_reject_runs_one_revision_then_completes_when_limit_is_exhausted(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
        _write_matching_evidence(repo, "Test revision")
        output = tmp_path / "output"
        reviews = 0

        def reject_review(_: dict[str, object]) -> dict[str, object]:
            nonlocal reviews
            reviews += 1
            return {
                "agent_id": "review-agent-v1",
                "role": "review",
                "output": {
                    "decision": "REJECT",
                    "summary": "Explicit mock rejection for revision coverage.",
                    "target_agent_id": "design-agent-v1",
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
            == 0
        )
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        assert reviews == 2
        assert manifest["workflow_state"] == "completed"
        assert manifest["revision_count"] == 1
        assert manifest["revision_exhausted"] is True
        assert [step[1] for step in manifest["workflow_history"]].count("revising") == 1
        run_dir = next(output.glob("run-multi-*"))
        outputs = json.loads((run_dir / "agent-outputs.json").read_text(encoding="utf-8"))
        assert "stage-1/design-agent-v1" in outputs
        assert "stage-4/design-agent-v1" in outputs
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
        _write_matching_evidence(repo, "Test")
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
        _write_matching_evidence(repo, "Test")
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
        _write_matching_evidence(repo, "Test required failure")
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
        _write_matching_evidence(repo, "Policy budget")
        policy = ExecutionPolicy(max_llm_calls=1)

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Policy budget",
                output=tmp_path / "output",
                mock=True,
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
        _write_matching_evidence(repo, "Parallel policy")
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
