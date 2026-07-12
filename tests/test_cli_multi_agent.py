"""Tests for multi-agent runner and CLI --mode multi-agent."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from specflow.plan.hash_utils import canonical_json_bytes
from specflow.policy.models import ExecutionPolicy
from specflow.runner_multi import _build_registry, _validated_inputs, run_multi_agent
from specflow.schema import build_schema_registry


class TestMultiAgentRunner:
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
        output = tmp_path / "output"
        exit_code = run_multi_agent(
            repo=repo, requirement="Add feature X", output=output, mock=True
        )
        assert exit_code == 0
        assert len(list(output.glob("run-multi-*"))) == 1

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

    def test_reject_runs_one_revision_then_completes_when_limit_is_exhausted(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "test-repo"
        repo.mkdir()
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
