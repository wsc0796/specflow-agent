"""Search excerpts may only bind to the same sanitized read snapshot."""

from hashlib import sha256

import pytest

from specflow.evidence import EvidenceCollector
from specflow.tools import ToolCall, ToolExecutor, ToolRegistry
from specflow.tools.repository_tools import RepositoryToolSet


def _executor(root, limits=None):
    registry = ToolRegistry()
    RepositoryToolSet(root, limits=limits).register_into(registry)
    return ToolExecutor(registry)


def _call(executor, name, **arguments):
    return executor.execute(ToolCall.build(call_id=name, tool_name=name, arguments=arguments))


@pytest.mark.parametrize("change_at", ["read", "second_search"])
def test_changed_source_is_not_paired_with_stale_excerpt(tmp_path, change_at):
    source = tmp_path / "app.py"
    source.write_bytes(b"def refund(): return 'ALLOW_OLD'\n")
    real = _executor(tmp_path)

    class ChangingExecutor:
        searches = 0

        def execute(self, call):
            if call.tool_name == "search_code":
                self.searches += 1
            if (change_at == "read" and call.tool_name == "read_file") or (
                change_at == "second_search"
                and call.tool_name == "search_code"
                and self.searches == 2
            ):
                source.write_bytes(b"def refund(): return 'DENY_NEW'\n")
            return real.execute(call)

    bundle = EvidenceCollector(ChangingExecutor(), tmp_path).collect(
        run_id="synthetic", requirement="refund return"
    )
    assert bundle.excerpts == ()
    assert "app.py" not in bundle.source_hashes
    assert bundle.warnings
    assert bundle.truncated
    assert "ALLOW_OLD" not in bundle.serialized_context()


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_unchanged_hash_covers_sanitized_read_snapshot(tmp_path, ending):
    source = tmp_path / "app.py"
    source.write_bytes(ending.join([b"# context", b"def refund(): return 'ok'", b"# trailer", b""]))
    real = _executor(tmp_path)
    match = _call(real, "search_code", query="refund").output["matches"][0]
    read = _call(real, "read_file", path="app.py").output
    assert match["content_hash"] == read["content_hash"]
    assert read["content_hash"] == sha256(read["content"].encode("utf-8")).hexdigest()
    assert read["content_hash"] != sha256(match["excerpt"].encode("utf-8")).hexdigest()
    bundle = EvidenceCollector(real, tmp_path).collect(run_id="synthetic", requirement="refund")
    assert len(bundle.excerpts) == 1
    assert bundle.excerpts[0].line_number == 2
    assert bundle.source_hashes["app.py"] == read["content_hash"]
    assert bundle.warnings == ()


def test_truncated_sanitized_snapshot_uses_same_hash_without_secrets(tmp_path):
    from specflow.tools.repository_policy import RepositoryPolicyLimits

    (tmp_path / "app.py").write_bytes(b'api_key="synthetic-secret" # refund\n' + b"# tail\n" * 20)
    real = _executor(tmp_path, RepositoryPolicyLimits(max_file_bytes=60))
    match = _call(real, "search_code", query="refund").output["matches"][0]
    read = _call(real, "read_file", path="app.py").output
    assert read["truncated"] is True
    assert match["content_hash"] == read["content_hash"]
    assert "synthetic-secret" not in match["excerpt"] + read["content"]
    bundle = EvidenceCollector(real, tmp_path).collect(run_id="synthetic", requirement="refund")
    assert bundle.excerpts
    assert bundle.truncated
    assert "synthetic-secret" not in bundle.serialized_context()


def test_missing_search_version_is_not_silently_bound(tmp_path):
    (tmp_path / "app.py").write_bytes(b"def refund(): pass\n")
    real = _executor(tmp_path)

    class MissingVersionExecutor:
        def execute(self, call):
            result = real.execute(call)
            if call.tool_name == "search_code":
                for match in result.output["matches"]:
                    match.pop("content_hash", None)
            return result

    bundle = EvidenceCollector(MissingVersionExecutor(), tmp_path).collect(
        run_id="synthetic", requirement="refund"
    )
    assert not bundle.excerpts
    assert not bundle.source_hashes
    assert bundle.warnings


def test_only_changed_source_stops_runner_before_planning(tmp_path, monkeypatch):
    import json

    from specflow import runner_multi

    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "app.py"
    source.write_bytes(b"def refund(): return 'ALLOW_OLD'\n")

    class ChangingExecutor(ToolExecutor):
        def execute(self, call):
            if call.tool_name == "read_file":
                source.write_bytes(b"def refund(): return 'DENY_NEW'\n")
            return super().execute(call)

    called = []
    monkeypatch.setattr(runner_multi, "ToolExecutor", ChangingExecutor)
    monkeypatch.setattr(runner_multi, "_make_mock_llm_client", lambda: called.append(True))
    output = tmp_path / "out"
    code = runner_multi.run_multi_agent(repo=repo, requirement="refund", output=output, mock=True)
    assert code == 3
    assert called == []
    manifest = json.loads(next(output.glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["error"] == "EVIDENCE_NOT_FOUND"
    assert manifest["stages_completed"] == 0
