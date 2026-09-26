"""The run deadline gates every Evidence Tool dispatch and returned result."""

import json

import pytest

from specflow import runner_multi
from specflow.policy import ExecutionPolicy, RuntimeGuard
from specflow.tools import ToolExecutor, ToolResult


@pytest.mark.parametrize("expire_at", ["before", "list_files", "search_code", "read_file"])
@pytest.mark.parametrize("failed_tool", [False, True])
def test_evidence_deadline_stops_further_tools_and_preserves_reason(
    tmp_path, monkeypatch, expire_at, failed_tool
):
    clock = [0.0]
    calls = []
    calls_after_deadline = []
    planning_calls = []

    def guard_factory(policy):
        guard = RuntimeGuard(policy, time_source=lambda: clock[0])
        if expire_at == "before":
            clock[0] = 1.0
        return guard

    class ExpiringExecutor(ToolExecutor):
        def execute(self, call):
            if clock[0] >= 1.0:
                calls_after_deadline.append(call.tool_name)
            calls.append(call.tool_name)
            result = super().execute(call)
            if call.tool_name == expire_at:
                clock[0] = 1.0
                if failed_tool:
                    return ToolResult.failed(
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        error_type="SyntheticFailure",
                        error_message="PRIVATE_TOOL_EXCEPTION",
                    )
            return result

    monkeypatch.setattr(runner_multi, "RuntimeGuard", guard_factory)
    monkeypatch.setattr(runner_multi, "ToolExecutor", ExpiringExecutor)
    monkeypatch.setattr(runner_multi, "_make_mock_llm_client", lambda: planning_calls.append(True))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_bytes(b"def refund(): return 'synthetic'\n")
    output = tmp_path / "out"
    assert (
        runner_multi.run_multi_agent(
            repo=repo,
            requirement="refund return",
            output=output,
            mock=True,
            policy=ExecutionPolicy(max_wall_time_seconds=1),
        )
        == 3
    )
    assert calls_after_deadline == []
    assert planning_calls == []
    if expire_at == "before":
        assert calls == []
    else:
        assert calls[-1] == expire_at
    run = next(output.glob("run-multi-*"))
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error"] == "TIME_BUDGET_EXCEEDED"
    assert manifest["workflow_state"] == "failed"
    assert manifest["stages_completed"] == 0
    assert manifest["tool_call_count"] == len(calls)
    assert manifest["failure_context"]["phase"] == "evidence_collection"
    assert "discovered_files" not in manifest  # no completed bundle to prove this count
    assert (run / "_COMPLETE").is_file()
    assert "PRIVATE_TOOL_EXCEPTION" not in (run / "manifest.json").read_text(encoding="utf-8")


def test_normal_zero_evidence_keeps_no_evidence_classification(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "unrelated.py").write_bytes(b"xyzzy\n")
    output = tmp_path / "out"
    assert (
        runner_multi.run_multi_agent(repo=repo, requirement="refund", output=output, mock=True) == 3
    )
    manifest = json.loads(next(output.glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["error"] == "EVIDENCE_NOT_FOUND"
    assert "failure_context" not in manifest
