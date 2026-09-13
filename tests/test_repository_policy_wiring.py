"""Execution-policy wiring for repository-bound Tools."""

from __future__ import annotations

import json
from pathlib import Path

from specflow.policy.models import ExecutionPolicy, RepositoryPolicy
from specflow.runner import run as run_legacy
from specflow.runner_multi import run_multi_agent


def _write_probe_repository(root: Path) -> Path:
    repo = root / "repository"
    repo.mkdir()
    (repo / "probe.py").write_text("token\nabcdefghij\n", encoding="utf-8")
    return repo


def _five_byte_policy() -> ExecutionPolicy:
    return ExecutionPolicy(repository=RepositoryPolicy(max_file_bytes=5))


def _read_file_records(run_dir: Path, key: str) -> list[dict[str, object]]:
    sources = json.loads((run_dir / "sources.json").read_text(encoding="utf-8"))
    return [record for record in sources[key] if record["tool_name"] == "read_file"]


def test_legacy_runner_applies_execution_policy_file_limit(tmp_path: Path) -> None:
    repo = _write_probe_repository(tmp_path)
    output = tmp_path / "legacy-output"

    exit_code = run_legacy(
        repo=repo,
        requirement="token",
        output=output,
        mock=True,
        policy=_five_byte_policy(),
    )

    assert exit_code == 0
    records = _read_file_records(next(output.glob("run-*")), "tool_call_records")
    assert records
    assert records[0]["truncated"] is True


def test_multi_agent_runner_applies_execution_policy_file_limit(tmp_path: Path) -> None:
    repo = _write_probe_repository(tmp_path)
    output = tmp_path / "multi-output"

    exit_code = run_multi_agent(
        repo=repo,
        requirement="token",
        output=output,
        mock=True,
        policy=_five_byte_policy(),
    )

    assert exit_code == 0
    records = _read_file_records(next(output.glob("run-multi-*")), "tool_calls")
    assert records
    assert records[0]["truncated"] is True
