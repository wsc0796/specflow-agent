"""Trace terminal status agrees with accepted-stage and failure semantics."""

import json

import pytest

from specflow import runner_multi


@pytest.mark.parametrize("state", ["normal", "degraded", "failed"])
def test_trace_matches_actual_run_acceptance_and_metrics(tmp_path, state):
    registry = runner_multi._build_registry()
    analyst = "repository-analyst-agent-v1"

    def execute(context):
        result = registry.get(analyst).execute(context)
        if state == "degraded":
            result["degraded"] = True
        elif state == "failed":
            result["success"] = False
            result["output"] = {"degraded": True, "error_code": "SCHEMA_VALIDATION_FAILED"}
        return result

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_bytes(b"# health endpoint\n")
    output = tmp_path / "out"
    code = runner_multi.run_multi_agent(
        repo=repo,
        requirement="health endpoint",
        output=output,
        mock=True,
        _executor_overrides={analyst: execute},
    )
    run = next(output.glob("run-multi-*"))
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    traces = json.loads((run / "traces.json").read_text(encoding="utf-8"))
    spans = [span for span in traces if "agent_id" in span]
    if state == "failed":
        assert code == 3
        assert manifest["workflow_state"] == "failed"
        assert manifest["stages_completed"] == 0
        assert len(spans) == 1
        assert spans[0]["status"] == "failed"
        assert spans[0]["metadata"]["error_code"] == "SCHEMA_VALIDATION_FAILED"
    else:
        assert code == 0
        assert manifest["workflow_state"] == "completed"
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["schema_validated_count"] == 6
        assert metrics["fallback_count"] == 0
        assert metrics["degraded_count"] == (1 if state == "degraded" else 0)
        assert len(spans) == 6
        for span in spans:
            expected = (
                "degraded" if state == "degraded" and span["agent_id"] == analyst else "success"
            )
            assert span["status"] == expected
