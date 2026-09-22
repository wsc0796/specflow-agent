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


def test_worker_uses_controlled_multi_agent_cap_and_rejects_wrong_inputs(tmp_path, monkeypatch):
    module, _, dataset_root, target, output = prepared_fixture(tmp_path)
    from specflow.evaluation.dataset_v1 import load_dev_dataset
    from specflow.runner import RequestObservation

    case = load_dev_dataset(dataset_root).cases[0]
    payload = module.build_adapter_input(
        case,
        repo=target,
        output=output / "rejected",
        provider="mock",
        model="mock-model",
        mode="multi-agent",
    )
    assert payload["max_files"] == 5
    calls = []

    def fake_run_multi_agent(**kwargs):
        calls.append(kwargs)
        kwargs["request_observer"](
            RequestObservation(
                worker="repository-analyst-agent-v1",
                call_index=1,
                model="mock-model",
                messages=(("user", "synthetic"),),
                temperature=0.0,
                max_tokens=3000,
                response_format="json",
            )
        )
        return 0

    monkeypatch.setattr(module, "run_multi_agent", fake_run_multi_agent)
    assert module.execute_worker(payload) == 0
    assert len(calls) == 1
    assert calls[0]["policy"].repository.max_selected_files == 5
    assert (
        json.loads((output / "rejected" / "llm-requests.json").read_text(encoding="utf-8"))[0][
            "receiver"
        ]
        == "repository-analyst-agent-v1"
    )

    wrong_cap = module.build_adapter_input(
        case,
        repo=target,
        output=output / "wrong-cap",
        provider="mock",
        model="mock-model",
        mode="multi-agent",
    )
    wrong_cap["max_files"] = 10
    with pytest.raises(ValueError, match="frozen product input"):
        module.execute_worker(wrong_cap)

    payload = module.build_adapter_input(
        case,
        repo=target,
        output=output / "extra-field",
        provider="mock",
        model="mock-model",
        mode="legacy",
    )
    payload["gold_evidence"] = ["EVALUATOR_ONLY_MARKER"]
    with pytest.raises(ValueError, match="fields"):
        module.execute_worker(payload)
    assert not (output / "extra-field").exists()


def test_prepare_multi_agent_reuses_identity_and_blocks_pending_fairness(tmp_path):
    module, workspace, dataset, target, legacy_output = prepared_fixture(tmp_path)
    module.freeze_run_identity(legacy_output, provider="mock", model="mock-model")
    output = workspace / "data" / "day11" / "multi-agent-dev"

    config = module.prepare_multi_agent_baseline(
        workspace,
        dataset,
        target,
        output,
        legacy_config=legacy_output / "run-config.json",
    )

    assert config["mode"] == "multi-agent"
    assert config["provider"] == "mock"
    assert config["model"] == "mock-model"
    assert config["run_identity_frozen"] is False
    assert config["product_default_multi_agent_limits"]["max_selected_files"] == 10
    assert config["effective_multi_agent_limits"]["max_selected_files"] == 5
    assert config["fairness_decision"]["multi_agent_product_default_max_selected_files"] == 10
    assert config["fairness_decision"]["multi_agent_benchmark_max_selected_files"] == 5
    assert config["fairness_decision"]["status"] == "pending_learner_decision"
    assert json.loads((output / "prepared.json").read_text(encoding="utf-8")) == {
        "status": "prepared_only",
        "planned_count": 20,
        "attempted_count": 0,
        "not_started_count": 20,
        "holdout_opened": False,
        "blockers": [
            "Run identity is not frozen for the Day 11 code revision.",
            "Fairness decision is pending learner review.",
        ],
    }
    module.freeze_run_identity(output, provider="mock", model="mock-model")
    with pytest.raises(ValueError, match="Fairness"):
        module.run_prepared(output)


def test_controlled_cap_is_approved_and_as_is_is_not_an_official_day11_run(tmp_path, monkeypatch):
    module, workspace, dataset, target, legacy_output = prepared_fixture(tmp_path)
    module.freeze_run_identity(legacy_output, provider="mock", model="mock-model")

    equalize_output = workspace / "data" / "day11" / "equalize"
    module.prepare_multi_agent_baseline(
        workspace,
        dataset,
        target,
        equalize_output,
        legacy_config=legacy_output / "run-config.json",
    )
    module.freeze_run_identity(equalize_output, provider="mock", model="mock-model")
    equalize = module.record_fairness_decision(equalize_output, "controlled-cap-at-5")
    assert equalize["fairness_decision"]["status"] == "approved"
    assert equalize["product_default_multi_agent_limits"]["max_selected_files"] == 10
    assert equalize["effective_multi_agent_limits"]["max_selected_files"] == 5

    monkeypatch.setattr(module, "launch_worker", lambda _: 0)
    report = module.run_prepared(equalize_output)
    assert report["summary"]["attempted_count"] == 20
    assert report["summary"]["not_started_count"] == 0
    assert report["config"]["product_default_multi_agent_limits"]["max_selected_files"] == 10
    assert report["config"]["effective_multi_agent_limits"]["max_selected_files"] == 5
    assert (equalize_output / "multi-agent-dev-report.json").is_file()
    assert not (equalize_output / "legacy-dev-report.json").exists()

    as_is_output = workspace / "data" / "day11" / "as-is"
    module.prepare_multi_agent_baseline(
        workspace,
        dataset,
        target,
        as_is_output,
        legacy_config=legacy_output / "run-config.json",
    )
    module.freeze_run_identity(as_is_output, provider="mock", model="mock-model")
    as_is = module.record_fairness_decision(as_is_output, "current-topology-as-is")
    assert as_is["fairness_decision"]["status"] == "not_selected_for_official_day11"
    assert "fact_evidence_coverage" in as_is["fairness_decision"]["not_comparable_dimensions"]
    with pytest.raises(ValueError, match="official Day 11"):
        module.run_prepared(as_is_output)
    assert not (as_is_output / "attempts.json").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("missing_effective_cap", None),
        ("effective_cap", 6),
        ("product_default_cap", 11),
    ],
)
def test_controlled_cap_config_drift_fails_before_worker_launch(
    tmp_path, monkeypatch, field, value
):
    module, workspace, dataset, target, legacy_output = prepared_fixture(tmp_path)
    module.freeze_run_identity(legacy_output, provider="mock", model="mock-model")
    output = workspace / "data" / "day11" / "controlled-cap-drift"
    module.prepare_multi_agent_baseline(
        workspace,
        dataset,
        target,
        output,
        legacy_config=legacy_output / "run-config.json",
    )
    module.freeze_run_identity(output, provider="mock", model="mock-model")
    module.record_fairness_decision(output, "controlled-cap-at-5")

    config_path = output / "run-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if field == "missing_effective_cap":
        config["effective_multi_agent_limits"].pop("max_selected_files")
    elif field == "effective_cap":
        config["effective_multi_agent_limits"]["max_selected_files"] = value
    else:
        config["product_default_multi_agent_limits"]["max_selected_files"] = value
    config_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setattr(
        module,
        "launch_worker",
        lambda _: pytest.fail("Invalid cap configuration must fail before worker launch"),
    )
    with pytest.raises(ValueError, match="controlled benchmark configuration"):
        module.run_prepared(output)
    assert not (output / "attempts.json").exists()


def test_existing_attempts_block_controlled_cap_before_worker_launch(tmp_path, monkeypatch):
    module, workspace, dataset, target, legacy_output = prepared_fixture(tmp_path)
    module.freeze_run_identity(legacy_output, provider="mock", model="mock-model")
    output = workspace / "data" / "day11" / "controlled-cap-attempts"
    module.prepare_multi_agent_baseline(
        workspace,
        dataset,
        target,
        output,
        legacy_config=legacy_output / "run-config.json",
    )
    module.freeze_run_identity(output, provider="mock", model="mock-model")
    module.record_fairness_decision(output, "controlled-cap-at-5")
    (output / "attempts.json").write_text("[]\n", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "launch_worker",
        lambda _: pytest.fail("Existing attempts must fail before worker launch"),
    )
    with pytest.raises(ValueError, match="Existing attempts"):
        module.run_prepared(output)


def test_multi_agent_summary_does_not_treat_agent_usage_as_full_cost():
    module = baseline_module()
    report = module.summarize_attempts(
        ["A"],
        [
            {
                "case_id": "A",
                "wall_time_ms": 10,
                "product_terminal_state": "completed",
                "usage_observation": {
                    "request_count": 12,
                    "metered_agent_request_count": 6,
                    "unmetered_enrichment_request_count": 6,
                    "observed_input_tokens_subtotal": 30,
                    "observed_output_tokens_subtotal": 20,
                    "observed_total_tokens_subtotal": 50,
                    "all_provider_usage_complete": False,
                },
            }
        ],
        mode="multi-agent",
    )
    assert report["token_cost"]["observed_total_tokens_subtotal"] == 50
    assert report["token_cost"]["complete_run_count"] == 0
    assert report["token_cost"]["telemetry_coverage"] == 0.0
    assert report["token_cost"]["full_total"] == "unknown"
    assert report["token_cost"]["comparison_status"] == "not_comparable"


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
