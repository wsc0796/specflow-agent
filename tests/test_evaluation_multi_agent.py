import json

from specflow.evaluation.multi_agent_runner import (
    AB_DIMENSIONS,
    compare_legacy_vs_multi_agent,
)


class TestMultiAgentEvaluation:
    def test_ab_dimensions_count(self):
        assert len(AB_DIMENSIONS) == 10

    def test_ab_dimensions_all_unique_keys(self):
        keys = [d.key for d in AB_DIMENSIONS]
        assert len(keys) == len(set(keys))

    def test_all_max_scores_are_2(self):
        for d in AB_DIMENSIONS:
            assert d.max_score == 2

    def test_comparison_result_improvement(self):
        legacy = {
            "dimensions": [
                {"key": "requirement_coverage", "score": 1},
                {"key": "risk_coverage", "score": 1},
            ]
        }
        multi = {
            "case_id": "test",
            "dimensions": [
                {"key": "requirement_coverage", "score": 2},
                {"key": "risk_coverage", "score": 2},
            ],
        }
        result = compare_legacy_vs_multi_agent(legacy, multi)
        assert result.legacy_total == 2
        assert result.multi_agent_total == 4
        assert result.improvement == 2

    def test_summary_format(self):
        legacy = {"dimensions": []}
        multi = {"case_id": "test", "dimensions": []}
        result = compare_legacy_vs_multi_agent(legacy, multi)
        assert "Legacy: 0/20" in result.summary
        assert "Multi-Agent: 0/20" in result.summary

    def test_legacy_baseline_runs_in_mock_mode(self, tmp_path):
        """Verify legacy pipeline still runs end-to-end in mock mode."""
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo\n\nPython project.")
        from specflow.runner import run as legacy_run

        output = tmp_path / "legacy-output"
        exit_code = legacy_run(
            repo=repo, requirement="Add search endpoint", output=output, mock=True
        )
        assert exit_code in (0, 4)  # 0=clean, 4=degraded (known scanner gap)
        assert output.exists()

    def test_multi_agent_mock_mode_has_plan(self, tmp_path):
        """Verify multi-agent mock mode produces a valid plan manifest."""
        repo = tmp_path / "test-repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Test Repo")
        from specflow.runner_multi import run_multi_agent

        output = tmp_path / "multi-output"
        exit_code = run_multi_agent(repo=repo, requirement="Add X", output=output, mock=True)
        assert exit_code == 0
        manifests = list(output.glob("*-manifest.json"))
        assert len(manifests) == 1
        manifest = json.loads(manifests[0].read_text())
        assert len(manifest["stages"]) == 4
