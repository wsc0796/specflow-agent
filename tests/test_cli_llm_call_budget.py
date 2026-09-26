"""CLI budgets reach the real multi-agent runtime without real HTTP."""

import json

import pytest
from test_multi_agent_request_budget import FakeProvider

from specflow import cli, runner_multi


@pytest.mark.parametrize(("cap", "exit_code", "calls"), [(12, 0, 12), (10, 3, 10), (None, 3, 10)])
def test_cli_budget_controls_actual_provider_requests(tmp_path, monkeypatch, cap, exit_code, calls):
    provider = FakeProvider()
    monkeypatch.setattr(runner_multi, "_create_real_llm_client", lambda *a, **k: provider)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# explain health endpoint\n", encoding="utf-8")
    output = tmp_path / "out"
    args = [
        "run",
        "--repo",
        str(repo),
        "--output",
        str(output),
        "--requirement",
        "explain health endpoint",
        "--mode",
        "multi-agent",
        "--provider",
        "openai-compatible",
        "--model",
        "fake",
    ]
    if cap is not None:
        args += ["--max-llm-calls", str(cap)]
    with pytest.raises(SystemExit) as raised:
        cli.main(args)
    assert raised.value.code == exit_code
    assert len(provider.requests) == calls
    manifest = json.loads(next(output.glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["budget_usage"]["llm_calls"] == calls
    if exit_code == 3:
        assert manifest["error"] == "CALL_BUDGET_EXCEEDED"
    else:
        assert manifest["workflow_state"] == "completed"


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "abc"])
def test_invalid_cli_budget_is_rejected_before_execution(monkeypatch, value):
    called = []
    monkeypatch.setattr(runner_multi, "run_multi_agent", lambda **kwargs: called.append(kwargs))
    with pytest.raises(SystemExit) as raised:
        cli.main(
            [
                "run",
                "--repo",
                ".",
                "--requirement",
                "synthetic",
                "--mode",
                "multi-agent",
                "--max-llm-calls",
                value,
            ]
        )
    assert raised.value.code == 2
    assert called == []


def test_legacy_rejects_multi_agent_budget_instead_of_ignoring_it(monkeypatch):
    import specflow.runner

    called = []
    monkeypatch.setattr(specflow.runner, "run", lambda **kwargs: called.append(kwargs))
    with pytest.raises(SystemExit) as raised:
        cli.main(["run", "--repo", ".", "--requirement", "synthetic", "--max-llm-calls", "12"])
    assert raised.value.code == 2
    assert called == []
