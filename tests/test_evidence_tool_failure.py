"""Evidence failures retain a safe reason and bounded early-failure artifacts."""

import json

import pytest

from specflow import runner_multi
from specflow.tools.exceptions import RepositoryLimitError
from specflow.tools.repository_tools import ListFilesTool


@pytest.mark.parametrize("failure", ["list", "collection", "setup", "unknown_tool_type"])
def test_evidence_failure_is_persisted_without_losing_reason(
    tmp_path, monkeypatch, caplog, failure
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# health\n", encoding="utf-8")
    output = tmp_path / "out"
    exception_type = RepositoryLimitError
    if failure == "unknown_tool_type":
        exception_type = type("PRIVATE_TOOL_TYPE", (Exception,), {})

    def fail(*args, **kwargs):
        raise exception_type("PRIVATE_FAILURE_DETAIL C:/private-repository")

    if failure in {"list", "unknown_tool_type"}:
        monkeypatch.setattr(ListFilesTool, "execute", fail)
    elif failure == "collection":
        monkeypatch.setattr(runner_multi.EvidenceCollector, "collect", fail)
    else:
        monkeypatch.setattr(runner_multi, "RepositoryToolSet", fail)
    monkeypatch.setattr(
        runner_multi, "_make_mock_llm_client", lambda: pytest.fail("Must not start planning")
    )
    assert (
        runner_multi.run_multi_agent(repo=repo, requirement="health", output=output, mock=True) == 3
    )
    manifests = list(output.glob("*/manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["error"] == "EVIDENCE_COLLECTION_FAILED"
    assert manifest["stages_completed"] == 0
    assert manifest["tool_call_count"] == (1 if failure in {"list", "unknown_tool_type"} else 0)
    assert "discovered_files" not in manifest
    context = manifest["failure_context"]
    assert context["phase"] == "evidence_collection"
    if failure in {"list", "unknown_tool_type"}:
        assert context["tool_name"] == "list_files"
        assert context["error_type"] == (
            "RepositoryLimitError" if failure == "list" else "ToolExecutionError"
        )
    assert (manifests[0].parent / "_COMPLETE").is_file()
    assert (manifests[0].parent / "artifact-integrity.json").is_file()
    combined = json.dumps(manifest) + caplog.text
    assert "PRIVATE" not in combined
    assert "private-repository" not in combined
    assert "NoneType" not in combined
