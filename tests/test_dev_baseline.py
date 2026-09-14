"""Observe the real Legacy boundary without scoring mock text as task success."""

import importlib.util
import json
from dataclasses import FrozenInstanceError

import pytest

import specflow.runner as legacy


def baseline_module():
    assert importlib.util.find_spec("specflow.evaluation.dev_baseline") is not None, (
        "The Dev harness must keep attempts and observation separate from product artifacts"
    )
    from specflow.evaluation import dev_baseline

    return dev_baseline


def test_observer_sees_real_requests_without_injecting_collector_excerpts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health(): return 'REPOSITORY_EXCERPT_MARKER'\n")
    observations = []
    observed = tmp_path / "observed"
    plain = tmp_path / "plain"
    assert legacy.run(repo=repo, requirement="Explain health", output=plain, mock=True) == 0
    assert (
        legacy.run(
            repo=repo,
            requirement="Explain health",
            output=observed,
            mock=True,
            request_observer=observations.append,
        )
        == 0
    )
    assert [o.worker for o in observations] == ["analyze", "generate", "review"]
    assert all(o.call_index == 1 for o in observations)
    assert all("REPOSITORY_EXCERPT_MARKER" not in str(o.messages) for o in observations)
    sources = next(observed.glob("run-*/sources.json")).read_text(encoding="utf-8")
    assert "REPOSITORY_EXCERPT_MARKER" in sources
    for name in ("analysis.json", "generation.json", "review.json"):
        assert next(plain.glob(f"run-*/{name}")).read_text(encoding="utf-8") == next(
            observed.glob(f"run-*/{name}")
        ).read_text(encoding="utf-8")
    plain_sources = json.loads(next(plain.glob("run-*/sources.json")).read_text(encoding="utf-8"))
    assert plain_sources["excerpts"] == json.loads(sources)["excerpts"]
    with pytest.raises(FrozenInstanceError):
        observations[0].worker = "mutated"
    assert isinstance(observations[0].messages, tuple)


def test_observer_error_does_not_trigger_product_retry(tmp_path, caplog):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# health endpoint\n")
    calls = []

    def broken_observer(observation):
        calls.append(observation)
        raise RuntimeError("observer failed")

    assert (
        legacy.run(
            repo=repo,
            requirement="Explain health",
            output=tmp_path / "out",
            mock=True,
            request_observer=broken_observer,
        )
        == 0
    )
    assert len(calls) == 3
    assert "observation" in caplog.text


def test_unknown_cost_and_semantics_are_not_overwritten_by_success():
    module = baseline_module()
    report = module.summarize_attempts(
        ["A", "B", "C"],
        [
            {
                "case_id": "A",
                "exit_code": 0,
                "wall_time_ms": 10,
                "product_terminal_state": "completed",
            },
            {
                "case_id": "B",
                "exit_code": 3,
                "wall_time_ms": 20,
                "product_terminal_state": "unknown",
            },
        ],
    )
    assert (report["planned_count"], report["attempted_count"], report["not_started_count"]) == (
        3,
        2,
        1,
    )
    assert report["latency_ms"]["mean"] == 15
    assert report["token_cost"]["full_total"] == "unknown"
    assert report["token_cost"]["comparison_status"] == "not_comparable"
    assert report["task_success"] == {"pass": 0, "fail": 0, "unknown": 2, "N/A": 0}


def prepared_fixture(tmp_path):
    import subprocess

    from test_dataset_v1 import make_dataset, make_repository

    module = baseline_module()
    assert hasattr(module, "prepare_baseline"), "Dev needs a non-executing prepare stage"
    workspace, revision = make_repository(tmp_path / "workspace")
    dataset = make_dataset(workspace / "dataset", revision)
    subprocess.run(["git", "-C", str(workspace), "add", "dataset/dev.json"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "freeze synthetic dev",
        ],
        check=True,
    )
    freeze = subprocess.check_output(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    manifest["freeze_commit"] = freeze
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    target = workspace / "data" / "day10" / "target"
    output = workspace / "data" / "day10" / "baseline"
    module.prepare_baseline(workspace, dataset, target, output)
    return module, workspace, dataset, target, output


def test_prepare_does_not_run_product_and_day11_mirror_matches(tmp_path):
    module, _, _, target, output = prepared_fixture(tmp_path)
    config = json.loads((output / "run-config.json").read_text(encoding="utf-8"))
    mirror = json.loads((output / "day11-mirror-config.json").read_text(encoding="utf-8"))
    assert config["mode"] == "legacy"
    assert mirror["mode"] == "multi-agent"
    assert {k: v for k, v in config.items() if k != "mode"} == {
        k: v for k, v in mirror.items() if k != "mode"
    }
    assert config["provider"] == "unknown"
    assert config["planned_ids"] == [f"SF-RT-D{i:03}" for i in range(1, 21)]
    assert not (target / "docs").exists()
    assert not (output / "attempts.json").exists()
    with pytest.raises(ValueError, match="identity"):
        module.run_prepared(output)


def test_child_receives_no_annotations_and_records_actual_messages(tmp_path):
    module, _, dataset_root, target, output = prepared_fixture(tmp_path)
    from specflow.evaluation.dataset_v1 import load_dev_dataset

    case = load_dev_dataset(dataset_root).cases[0]
    run_output = output / "single-synthetic"
    payload = module.build_adapter_input(
        case, repo=target, output=run_output, provider="mock", model="mock-model", mode="legacy"
    )
    assert set(payload) == {
        "mode",
        "repo",
        "output",
        "provider",
        "model",
        "max_files",
        "requirement",
    }
    assert "EVALUATOR_ONLY_MARKER" not in json.dumps(payload)
    payload_path = output / "synthetic-input.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    result = module.launch_worker(payload_path)
    assert result == 0
    observations = json.loads((run_output / "llm-requests.json").read_text(encoding="utf-8"))
    assert [o["worker"] for o in observations] == ["analyze", "generate", "review"]
    assert "EVALUATOR_ONLY_MARKER" not in json.dumps(observations)
    inspection = module.inspect_attempt(run_output, target)
    assert inspection["product_terminal_state"] == "completed"
    assert inspection["evaluator_results"]["task_success"]["verdict"] == "unknown"
    assert inspection["observation_status"] == "complete"


def test_worker_rejects_extra_fields_and_multi_agent_before_product(tmp_path):
    module, _, dataset_root, target, output = prepared_fixture(tmp_path)
    from specflow.evaluation.dataset_v1 import load_dev_dataset

    case = load_dev_dataset(dataset_root).cases[0]
    payload = module.build_adapter_input(
        case,
        repo=target,
        output=output / "rejected",
        provider="mock",
        model="mock-model",
        mode="multi-agent",
    )
    with pytest.raises(ValueError, match="Day 11"):
        module.execute_worker(payload)
    payload["mode"] = "legacy"
    payload["gold_evidence"] = ["EVALUATOR_ONLY_MARKER"]
    with pytest.raises(ValueError, match="fields"):
        module.execute_worker(payload)
    assert not (output / "rejected").exists()


def test_attempt_journal_keeps_failure_degraded_and_interruption(tmp_path, monkeypatch):
    module, _, _, _, output = prepared_fixture(tmp_path)
    module.freeze_run_identity(output, provider="mock", model="mock-model")
    codes = iter([0, 4, 3, KeyboardInterrupt()])

    def launch(path):
        journal = json.loads((output / "attempts.json").read_text(encoding="utf-8"))
        assert journal[-1]["attempt_status"] == "started"
        code = next(codes)
        if isinstance(code, BaseException):
            raise code
        return code

    monkeypatch.setattr(module, "launch_worker", launch)
    report = module.run_prepared(output)
    assert (report["summary"]["attempted_count"], report["summary"]["not_started_count"]) == (4, 16)
    assert [a["exit_code"] for a in report["attempts"]] == [0, 4, 3, None]
    assert report["attempts"][-1]["attempt_status"] == "interrupted"
    assert len({a["attempt_id"] for a in report["attempts"]}) == 4
    assert report["summary"]["task_success"]["unknown"] == 4
    with pytest.raises(ValueError, match="attempt"):
        module.run_prepared(output)


def test_zero_attempts_and_incomplete_observation_are_explicit(tmp_path):
    module = baseline_module()
    report = module.summarize_attempts(["A"], [])
    assert report["token_cost"]["telemetry_coverage"] == "N/A"
    inspection = module.inspect_attempt(tmp_path / "missing", tmp_path)
    assert inspection["product_terminal_state"] == "unknown"
    assert inspection["observation_status"] == "unknown"


def test_live_model_mismatch_fails_before_provider_call(tmp_path, monkeypatch):
    module, _, _, _, output = prepared_fixture(tmp_path)
    monkeypatch.setenv("SPECFLOW_LLM_MODEL", "actual-model")
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", "synthetic-key")
    monkeypatch.setenv("SPECFLOW_LLM_BASE_URL", "https://provider.invalid/v1")
    with pytest.raises(ValueError, match="model"):
        module.freeze_run_identity(output, provider="openai-compatible", model="different-model")
    assert not (output / "attempts.json").exists()


def test_changed_frozen_dev_is_rejected_before_any_attempt(tmp_path, monkeypatch):
    module, _, dataset, _, output = prepared_fixture(tmp_path)
    module.freeze_run_identity(output, provider="mock", model="mock-model")

    def deny_launch(path):
        pytest.fail("Preflight failure must not launch a product process")

    monkeypatch.setattr(module, "launch_worker", deny_launch)
    dev = json.loads((dataset / "dev.json").read_text(encoding="utf-8"))
    dev["cases"][0]["gold_evidence"] = [{"fact_id": "CHANGED_GOLD"}]
    (dataset / "dev.json").write_text(json.dumps(dev), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen"):
        module.run_prepared(output)
    assert not (output / "attempts.json").exists()


def test_missing_request_file_invalidates_observation_claim(tmp_path):
    module = baseline_module()
    (tmp_path / "observation-status.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "observed_call_count": 3,
            }
        ),
        encoding="utf-8",
    )
    assert module.inspect_attempt(tmp_path, tmp_path)["observation_status"] == "incomplete"


def test_cli_reports_missing_live_identity_without_traceback(tmp_path, monkeypatch, capsys):
    module, _, _, _, output = prepared_fixture(tmp_path)
    for name in ("SPECFLOW_LLM_MODEL", "SPECFLOW_LLM_API_KEY", "SPECFLOW_LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert (
        module.main(
            [
                "--output",
                str(output),
                "--freeze-identity",
                "--provider",
                "openai-compatible",
                "--model",
                "configured-model",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_cli_rejects_ignored_execution_model_override(tmp_path, monkeypatch):
    module, _, _, _, output = prepared_fixture(tmp_path)
    module.freeze_run_identity(output, provider="mock", model="mock-model")

    def deny_launch(path):
        pytest.fail("An ignored model option must never launch the product")

    monkeypatch.setattr(module, "launch_worker", deny_launch)
    assert module.main(["--output", str(output), "--execute", "--model", "ignored-model"]) == 2
    assert not (output / "attempts.json").exists()


def test_provider_error_is_preserved_and_budget_rejection_is_not_observed():
    from specflow.llm import LLMMessage, LLMRequest
    from specflow.llm.exceptions import LLMTimeoutError
    from specflow.policy import ExecutionBudget, ExecutionPolicy

    request = LLMRequest(model="test-model", messages=[LLMMessage(role="user", content="hello")])
    seen = []
    forwarded = []
    error = LLMTimeoutError("synthetic timeout")

    class Provider:
        def complete(self, value):
            forwarded.append(value)
            raise error

    budget = ExecutionBudget(ExecutionPolicy(max_llm_calls=1))
    client = legacy._PolicyBoundLLMClient(
        Provider(), budget, worker="analyze", observer=seen.append
    )
    with pytest.raises(LLMTimeoutError) as failure:
        client.complete(request)
    assert failure.value is error
    assert forwarded == [request]
    assert forwarded[0] is request
    with pytest.raises(Exception) as rejected:
        client.complete(request)
    assert not isinstance(rejected.value, LLMTimeoutError)
    assert len(seen) == 1
