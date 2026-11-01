"""Offline trial controls and actual API wiring, never a paid model invocation."""

import copy
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity
from specflow.contract_review.provider import ProviderFailure
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.main import create_app

REPO = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPO / "scripts" / "contract_review"


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = load_script("f01_trial_guard", "f01_trial_guard.py")
pilot = load_script("f01_pilot", "run_f01_pilot.py")


@pytest.fixture(autouse=True)
def approved_execution_time(monkeypatch):
    monkeypatch.setattr(guard, "utc_now", lambda: datetime(2026, 11, 1, 10, 30, tzinfo=UTC))


def response(*, usage=True, model="deepseek-flash"):
    body = {"model": model, "choices": [{"message": {"content": '{"ok": true}'}}]}
    if usage:
        body["usage"] = {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
    return httpx.Response(200, json=body)


@pytest.fixture
def adapter_factory(tmp_path):
    ledgers = []

    def make(handler=None, *, policy=None):
        policy = policy or guard.FlashPolicy(
            input_token_bound=128, evidence="controlled-offline-only"
        )
        ledger = guard.TrialLedger(policy, tmp_path / f"trial-{len(ledgers)}.jsonl")
        ledgers.append(ledger)
        calls = []

        def handle(request):
            calls.append(request)
            return handler(request) if handler else response()

        config = OpenAICompatibleConfig(
            "https://offline.invalid", "synthetic-trial-secret", guard.REQUEST_MODEL, 5
        )
        adapter = guard.GuardedFlashAdapter(
            config, ledger, transport=httpx.MockTransport(handle), execution_mode="test"
        )
        profile = pilot.make_profile(adapter)
        wire = {
            "model": guard.REQUEST_MODEL,
            "temperature": 0.0,
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": "Return JSON."}],
        }
        return adapter, ledger, profile, wire, calls

    yield make
    for ledger in ledgers:
        ledger.close()


def test_cny_one_cannot_cover_the_demonstrated_context_bound():
    policy = guard.FlashPolicy(budget_cny=Decimal("1"))
    assert policy.quote() == Decimal("1.080576")
    assert policy.record()["currency"] == "CNY"
    assert policy.record()["billing_basis"].startswith("off-peak")
    with pytest.raises(guard.TrialStopped, match="BUDGET_PRECHECK_FAILED"):
        policy.require_first_dispatch()


def test_current_cny_two_grant_covers_first_off_peak_reservation():
    policy = guard.FlashPolicy()
    policy.require_first_dispatch()
    assert policy.budget_cny == Decimal("2")
    assert policy.quote() == Decimal("1.080576")


@pytest.mark.parametrize(
    ("instant", "allowed"),
    [
        (datetime(2026, 11, 1, 9, 59, 59, tzinfo=UTC), False),
        (datetime(2026, 11, 1, 10, tzinfo=UTC), True),
        (datetime(2026, 11, 1, 15, 59, 59, tzinfo=UTC), True),
        (datetime(2026, 11, 1, 16, tzinfo=UTC), False),
        (datetime(2026, 11, 2, 10, tzinfo=UTC), False),
        (datetime(2026, 11, 1, 10), False),
    ],
)
def test_off_peak_execution_window_boundaries(instant, allowed):
    if allowed:
        guard.require_execution_window(instant)
    else:
        with pytest.raises(guard.TrialStopped, match="TRIAL_OFF_PEAK_WINDOW_REQUIRED"):
            guard.require_execution_window(instant)


@pytest.mark.parametrize(
    "values",
    [
        {"budget_cny": Decimal("0")},
        {"budget_cny": Decimal("2.01")},
        {"budget_cny": Decimal("NaN")},
        {"call_limit": 13},
        {"call_limit": True},
        {"output_token_limit": 8001},
        {"input_token_bound": False},
    ],
)
def test_policy_cannot_expand_the_user_grant(values):
    with pytest.raises(ValueError):
        guard.FlashPolicy(**values)


def test_live_adapter_rejects_a_test_only_input_bound_and_other_channel(tmp_path):
    ledger = guard.TrialLedger(
        guard.FlashPolicy(input_token_bound=128, evidence="offline"), tmp_path / "test.jsonl"
    )
    try:
        config = OpenAICompatibleConfig(
            guard.PROVIDER_BASE, "synthetic-trial-secret", guard.REQUEST_MODEL, 5
        )
        with pytest.raises(ValueError, match="frozen official"):
            guard.GuardedFlashAdapter(config, ledger)
        config = OpenAICompatibleConfig(
            "https://another.invalid", "synthetic-trial-secret", guard.REQUEST_MODEL, 5
        )
        with pytest.raises(ValueError, match="frozen official"):
            guard.GuardedFlashAdapter(config, ledger)
    finally:
        ledger.close()


def test_currency_denial_occurs_before_any_transport(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory(
        policy=guard.FlashPolicy(budget_cny=Decimal("1"))
    )
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "TRIAL_FEE_LIMIT"
    assert error.value.remote_outcome == "not_applicable"
    assert error.value.usage == {"input_tokens": 0, "output_tokens": 0}
    assert calls == []
    assert ledger.summary()["model_call_reservations"] == 0


def test_window_denial_precedes_reservation_and_http(adapter_factory, monkeypatch):
    adapter, ledger, profile, wire, calls = adapter_factory()
    monkeypatch.setattr(guard, "utc_now", lambda: datetime(2026, 11, 1, 9, 59, tzinfo=UTC))
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "TRIAL_OFF_PEAK_WINDOW_REQUIRED"
    assert ledger.summary()["model_call_reservations"] == 0
    assert calls == []


def test_transport_rechecks_window_immediately_before_http(adapter_factory, monkeypatch):
    adapter, ledger, profile, wire, calls = adapter_factory()
    instants = iter(
        (datetime(2026, 11, 1, 15, 59, 59, tzinfo=UTC), datetime(2026, 11, 1, 16, tzinfo=UTC))
    )
    monkeypatch.setattr(guard, "utc_now", lambda: next(instants))
    with pytest.raises(ProviderFailure):
        adapter.complete(wire, profile=profile)
    assert ledger.summary()["model_call_reservations"] == 1
    assert ledger.summary()["business_model_http_attempts"] == 0
    assert calls == []


def test_complete_usage_releases_only_its_reservation(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory()
    assert adapter.complete(wire, profile=profile)["model"] == "deepseek-flash"
    summary = ledger.summary()
    assert summary["business_model_http_attempts"] == 1
    assert summary["cost_cny_upper_accounted"] == "0.000019"
    assert Decimal(summary["unsettled_cny_reserved"]) == 0
    assert summary["provider_invoice_cost"] is None
    assert len(calls) == 1
    journal = ledger._stream.name
    assert "synthetic-trial-secret" not in Path(journal).read_text(encoding="utf-8")


def test_missing_usage_retains_occupancy_and_blocks_the_next_call(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory(lambda _: response(usage=False))
    assert adapter.complete(wire, profile=profile)["usage"] == {}
    assert ledger.summary()["halt_reason"] == "TRIAL_USAGE_UNKNOWN"
    assert Decimal(ledger.summary()["unsettled_cny_reserved"]) == ledger.policy.quote()
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "TRIAL_USAGE_UNKNOWN"
    assert len(calls) == 1


def test_dependency_failure_has_no_automatic_retry(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory(
        lambda _: httpx.Response(429, text="untrusted upstream content")
    )
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "PROVIDER_RATE_LIMITED"
    assert error.value.retryable is False
    assert Decimal(ledger.summary()["unsettled_cny_reserved"]) == ledger.policy.quote()
    with pytest.raises(ProviderFailure):
        adapter.complete(wire, profile=profile)
    assert len(calls) == 1


def test_wrong_provider_model_is_preserved_but_not_accepted(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory(
        lambda _: response(model="deepseek-v4-pro")
    )
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "TRIAL_MODEL_MISMATCH"
    assert ledger.summary()["halt_reason"] == "TRIAL_MODEL_MISMATCH"
    assert len(calls) == 1
    assert "deepseek-v4-pro" in Path(ledger._stream.name).read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_response_model_identity_is_not_proved_by_adapter_fallback(adapter_factory, kind):
    def handle(_):
        body = response().json()
        if kind == "missing":
            del body["model"]
        else:
            body["model"] = ""
        return httpx.Response(200, json=body)

    adapter, ledger, profile, wire, calls = adapter_factory(handle)
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "TRIAL_MODEL_UNKNOWN"
    assert ledger.summary()["halt_reason"] == "TRIAL_MODEL_UNKNOWN"
    assert Decimal(ledger.summary()["unsettled_cny_reserved"]) == ledger.policy.quote()
    assert Decimal(ledger.summary()["cost_cny_upper_accounted"]) == 0
    events = [json.loads(line) for line in Path(ledger._stream.name).read_text().splitlines()]
    identity = next(event for event in events if event["event"] == "http_response_identity")
    assert identity["model_field_present"] is (kind == "empty")
    assert identity["model_field_valid"] is False
    with pytest.raises(ProviderFailure):
        adapter.complete(wire, profile=profile)
    assert len(calls) == 1


def test_model_bound_violation_is_not_settled_as_a_valid_charge(adapter_factory):
    def handler(_):
        result = response().json()
        result["usage"] = {"prompt_tokens": 129, "completion_tokens": 4, "total_tokens": 133}
        return httpx.Response(200, json=result)

    adapter, ledger, profile, wire, _ = adapter_factory(handler)
    with pytest.raises(ProviderFailure, match="模型依赖"):
        adapter.complete(wire, profile=profile)
    assert ledger.summary()["halt_reason"] == "TRIAL_USAGE_BOUND_VIOLATION"
    assert Decimal(ledger.summary()["unsettled_cny_reserved"]) > 0


def test_physical_attempt_cap_covers_every_complete_call(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory()
    for _ in range(12):
        adapter.complete(wire, profile=profile)
    with pytest.raises(ProviderFailure) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "TRIAL_CALL_LIMIT"
    assert len(calls) == 12
    assert ledger.summary()["business_model_http_attempts"] == 12


def test_profile_mismatch_never_reaches_http_or_reservation(adapter_factory):
    adapter, ledger, profile, wire, calls = adapter_factory()
    wire["model"] = "unapproved-model"
    with pytest.raises(Exception) as error:
        adapter.complete(wire, profile=profile)
    assert error.value.code == "RETRY_PROFILE_UNAVAILABLE"
    assert calls == []
    assert ledger.summary()["model_call_reservations"] == 0


def test_original_case_copy_contains_four_sources_and_two_targets(tmp_path):
    case = pilot.load_case(REPO)
    case_root, body = pilot.prepare_case(REPO, tmp_path, case)
    assert (
        body["source"]["commit_sha"] == pilot._git(case_root, "rev-parse", "HEAD").decode().strip()
    )
    assert {item["source_path"] for item in body["targets"]} == {
        "docs/api.md",
        "examples/client.py",
    }
    for path, _, fixture in pilot.MATERIALS:
        original = pilot._git(
            REPO,
            "show",
            f"{pilot.BASELINE}:benchmarks/contract_review/materials/{fixture}",
        )
        assert (case_root / path).read_bytes() == original
    assert not (case_root / "oracles.json").exists()
    assert not (case_root / "human-scripts.json").exists()


def test_public_run_is_blocked_before_auth_case_creation_and_api(tmp_path, monkeypatch):
    class PublicEnvironment(dict):
        def get(self, name, default=None):
            assert name != "ANTHROPIC_AUTH_TOKEN", "Preflight must not read credentials"
            return super().get(name, default)

    public = PublicEnvironment(
        {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if key in os.environ}
    )
    public.update(ANTHROPIC_BASE_URL=guard.LAUNCHER_BASE, ANTHROPIC_MODEL=guard.REQUEST_MODEL)
    monkeypatch.setattr(pilot.os, "environ", public)
    monkeypatch.setattr(pilot, "FlashPolicy", lambda: guard.FlashPolicy(budget_cny=Decimal("1")))
    monkeypatch.setattr(pilot, "_run_api", lambda *_: pytest.fail("API must not start"))
    monkeypatch.setattr(pilot, "prepare_case", lambda *_: pytest.fail("Case must not be created"))
    output = tmp_path / "run"
    result = pilot.run_pilot(REPO, output, live=True)
    assert result["status"] == "BLOCKED_BEFORE_DISPATCH"
    assert result["reason"] == "BUDGET_PRECHECK_FAILED"
    assert result["business_model_http_attempts"] == 0
    assert result["trial_consumed"] is False
    assert result["semantic_verdict"] == "NOT_RUN"
    assert list(p.name for p in output.iterdir()) == ["run.json"]
    before = (output / "run.json").read_bytes()
    with pytest.raises(FileExistsError):
        pilot.run_pilot(REPO, output, live=True)
    assert (output / "run.json").read_bytes() == before


def test_channel_mismatch_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://different.invalid/anthropic")
    result = pilot.run_pilot(REPO, tmp_path / "run", live=True)
    assert result["reason"] == "AUTHORIZED_CHANNEL_METADATA_MISMATCH"
    assert result["business_model_http_attempts"] == 0


def test_two_cny_preparation_does_not_load_auth_or_start_api(tmp_path, monkeypatch):
    class PublicEnvironment(dict):
        def get(self, name, default=None):
            assert name != "ANTHROPIC_AUTH_TOKEN"
            return super().get(name, default)

    public = PublicEnvironment(
        {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if key in os.environ}
    )
    public.update(ANTHROPIC_BASE_URL=guard.LAUNCHER_BASE, ANTHROPIC_MODEL=guard.REQUEST_MODEL)
    monkeypatch.setattr(pilot.os, "environ", public)
    monkeypatch.setattr(pilot, "_run_api", lambda *_: pytest.fail("Preparation cannot start API"))
    output = tmp_path / "prepare-only"
    result = pilot.run_pilot(REPO, output)
    assert result["status"] == "PREPARED_NOT_DISPATCHED"
    assert result["trial_policy"]["budget_cny"] == "2"
    assert result["trial_policy"]["reservation_cny"] == "1.080576"
    assert result["trial_consumed"] is False
    assert result["business_model_http_attempts"] == 0
    assert [p.name for p in output.iterdir()] == ["run.json"]


def test_trial_outputs_cannot_be_written_inside_the_product_checkout():
    with pytest.raises(guard.TrialStopped, match="OUTPUT_MUST_BE_OUTSIDE_CHECKOUT"):
        pilot.run_pilot(REPO, REPO / "unauthorized-pilot-output")


def test_api_worker_report_and_request_evidence_remain_distinct_from_semantic_pass(
    tmp_path, git_repo, controlled_adapter, adapter_factory
):
    controlled = controlled_adapter()

    def handle(request):
        wire = json.loads(request.content)
        result = controlled.complete(wire)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"content": result["content"]}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            },
        )

    adapter, ledger, profile, _, calls = adapter_factory(handle)
    root, _, body = git_repo
    body = copy.deepcopy(body)
    body.pop("project_id")
    body["execution_profile_id"] = pilot.PROFILE
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'pilot.sqlite').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        security=ApiSecurity(api_key="synthetic-local-key", allowed_repository_roots=(str(root),)),
        contract_review_profiles={pilot.PROFILE: profile},
        contract_review_adapter=adapter,
    )
    accepted_records = []
    with TestClient(app, headers={"X-API-Key": "synthetic-local-key"}) as client:
        result = pilot.submit_and_observe(
            client, root, body, seconds=10, interval=0.01, on_accept=accepted_records.append
        )
    assert result["status"]["status"] == "completed_degraded"
    assert result["supervision_timeout"] is False
    assert accepted_records[0]["accepted"] == result["accepted"]
    assert result["semantic_verdict"] == "PENDING_EVIDENCE_REVIEW"
    assert len(result["status"]["check_manifest"]) == 2
    assert result["collection_complete"] is True
    assert result["report_json"] and result["report_markdown"]
    assert len(calls) == ledger.summary()["business_model_http_attempts"] == 2
    projections = [
        event for event in result["events"] if event["event_type"] == "request_projected"
    ]
    assert len(projections) == 2
    assert all(event["payload"]["payload"]["messages"] for event in projections)
    assert result["accepted_to_terminal_observed_seconds"] >= 0


def test_journal_export_retains_uncleared_occupancy(tmp_path, adapter_factory):
    adapter, ledger, profile, wire, _ = adapter_factory(lambda _: response(usage=False))
    adapter.complete(wire, profile=profile)
    ledger.close()
    summary = pilot.trial_account(Path(ledger._stream.name).parent)
    # This helper uses the fixed runtime filename, not arbitrary trial test files.
    assert summary["ledger_available"] is False
    source = Path(ledger._stream.name)
    (tmp_path / "trial-ledger.jsonl").write_bytes(source.read_bytes())
    summary = pilot.trial_account(tmp_path)
    assert summary["business_model_http_attempts"] == 1
    assert Decimal(summary["unsettled_cny_reserved"]) > 0
    assert summary["provider_invoice_cost"] is None


def test_failed_child_is_joined_and_cleanup_is_recorded(tmp_path, monkeypatch):
    class FakeProcess:
        pid = 123
        exitcode = 0

        def start(self):
            pass

        def join(self, timeout):
            self.joined = True

        def is_alive(self):
            return False

    class FakeConnection:
        def poll(self, timeout):
            return True

        def recv(self):
            return {"error_code": "SYNTHETIC_START_FAILURE"}

        def close(self):
            pass

    class FakeContext:
        def Pipe(self, duplex):
            return FakeConnection(), FakeConnection()

        def Event(self):
            class Event:
                def set(self):
                    pass

            return Event()

        def Process(self, **kwargs):
            return FakeProcess()

    monkeypatch.setattr(pilot.multiprocessing, "get_context", lambda _: FakeContext())
    with pytest.raises(guard.TrialStopped, match="SYNTHETIC_START_FAILURE"):
        pilot._run_api(tmp_path, tmp_path / "case-repo", {})
    cleanup = json.loads((tmp_path / "cleanup.json").read_text(encoding="utf-8"))
    assert cleanup["local_process_exited"] is True
    assert cleanup["forced_stop"] is False


def test_call_identity_is_preserved_before_polling_can_fail():
    class Client:
        def post(self, path, **kwargs):
            if path.endswith("projects"):
                return httpx.Response(
                    201,
                    json={"id": "project"},
                    request=httpx.Request("POST", "http://local" + path),
                )
            return httpx.Response(
                202,
                json={"review_id": "review", "job_id": "job", "input_revision_id": "input"},
                request=httpx.Request("POST", "http://local" + path),
            )

        def get(self, path):
            raise httpx.ConnectError("controlled local polling failure")

    saved = []
    with pytest.raises(httpx.ConnectError):
        pilot.submit_and_observe(Client(), Path("unused"), {}, on_accept=saved.append)
    assert saved[0]["accepted"]["review_id"] == "review"
    assert saved[0]["submitted_body"]["project_id"] == "project"


def test_accepted_latency_excludes_the_submission_request(tmp_path, monkeypatch):
    clock = {"value": 100.0}

    class Client:
        def post(self, path, **kwargs):
            if path.endswith("projects"):
                body, status = {"id": "project"}, 201
            else:
                clock["value"] = 104.0
                body = {"review_id": "review", "job_id": "job", "input_revision_id": "input"}
                status = 202
            return httpx.Response(
                status, json=body, request=httpx.Request("POST", "http://local" + path)
            )

        def get(self, path):
            clock["value"] = 105.0
            return httpx.Response(
                200,
                json={"status": "completed"},
                request=httpx.Request("GET", "http://local" + path),
            )

    monkeypatch.setattr(pilot.time, "monotonic", lambda: clock["value"])
    monkeypatch.setattr(pilot, "collect_review", lambda *_: {})
    result = pilot.submit_and_observe(Client(), tmp_path, {})
    assert result["accepted_response_monotonic"] == 104
    assert result["submission_to_accepted_response_seconds"] == 4
    assert result["accepted_to_terminal_observed_seconds"] == 1
    assert result["submit_to_terminal_observed_seconds"] == 5
