"""Tests for multi-agent runner and CLI --mode multi-agent."""

import json
from pathlib import Path

from specflow.runner_multi import run_multi_agent


class TestMultiAgentRunner:
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
        assert len(traces) == 6
        assert len({trace["parent_span_id"] for trace in traces}) == 1
