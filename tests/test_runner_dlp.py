"""DLP boundaries shared by the legacy and multi-agent runners."""

from pathlib import Path

import specflow.runner as legacy_runner


def test_legacy_runner_applies_final_dlp_before_worker_context(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repository"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")
    output = tmp_path / "artifacts"
    scans: list[str] = []
    original_scan = legacy_runner.final_dlp_scan

    def record_scan(text: str) -> str:
        scans.append(text)
        return original_scan(text)

    monkeypatch.setattr(legacy_runner, "final_dlp_scan", record_scan)

    assert (
        legacy_runner.run(
            repo=repo,
            requirement="Add a health endpoint",
            output=output,
            mock=True,
        )
        == 0
    )
    assert len(scans) == 1
    assert "## Repository Evidence" in scans[0]
