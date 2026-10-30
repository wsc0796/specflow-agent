"""Controlled-adapter lifecycle evidence, never business-semantic acceptance."""

import json
import threading
import time

import pytest

from specflow.contract_review.common import ReviewError, digest, identity
from specflow.contract_review.execution import ExecutionLedger

URL = "/api/v1/contract-reviews"


def wait_status(client, review_id, expected):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        value = client.get(URL + "/" + review_id).json()
        if value["status"] in expected:
            return value
        time.sleep(0.01)
    pytest.fail(f"Did not reach {expected}: {value}")


def submit(client, body, key):
    response = client.post(URL, json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()


def test_intake_to_report_persists_calls_before_actual_adapter_and_returns_quality(
    running_app, controlled_adapter
):
    adapter = controlled_adapter()
    with running_app(adapter) as (client, domain, body):

        def durable_before_io(count):
            with domain.store.read() as conn:
                assert (
                    conn.exec_driver_sql(
                        "SELECT count(*) FROM contract_review_calls WHERE status='dispatch_started'"
                    ).scalar_one()
                    == 1
                )
                assert (
                    conn.exec_driver_sql(
                        "SELECT count(*) FROM contract_review_events WHERE "
                        "event_type='dispatch_intent'"
                    ).scalar_one()
                    == count
                )

        adapter.before_response = durable_before_io
        accepted = submit(client, body, "one")
        status = wait_status(client, accepted["review_id"], {"completed_degraded", "failed"})
        assert status["status"] == "completed_degraded", status
        assert status["quality"]["level"] == "degraded"
        report = client.get(URL + "/" + accepted["review_id"] + "/report").json()
        assert report["execution_mode"] == "test"
        assert report["input_revision_id"] == accepted["input_revision_id"]
        assert status["budget"]["model_calls"] == 2
        assert status["budget"]["input_tokens"] == 6
        assert status["budget"]["output_tokens"] == 8
        assert status["budget"]["usage_status"] == "known"
        assert len(adapter.requests) == 2
        with domain.store.read() as conn:
            calls = conn.exec_driver_sql("SELECT status,body FROM contract_review_calls").all()
            assert all(row.status == "accepted" for row in calls)
            assert all(json.loads(row.body)["local_io_state"] == "quiesced" for row in calls)
        events = client.get(URL + "/" + accepted["review_id"] + "/events?limit=100").json()["items"]
        assert [event["event_seq"] for event in events] == list(range(1, len(events) + 1))
        assert events[-1]["event_type"] == "report_committed"


def test_timeout_holds_slot_then_late_cleanup_resumes_queue_without_accepting_old_body(
    running_app, controlled_adapter
):
    release_first, release_second = threading.Event(), threading.Event()
    adapter = controlled_adapter({1: release_first, 2: release_second})
    with running_app(adapter, timeout=0.1) as (client, domain, body):
        first = submit(client, body, "first")
        assert adapter.entered[1].wait(2)
        failed = wait_status(client, first["review_id"], {"failed"})
        assert failed["error_code"] == "CALL_RESULT_UNKNOWN"
        blocker = failed["dispatch_gate"]["blocked_by"][0]
        second = submit(client, {**body, "execution_profile_id": "slow-test"}, "second")
        assert client.get(URL + "/" + second["review_id"]).json()["status"] == "queued"
        assert len(adapter.requests) == 1
        release_first.set()
        assert adapter.entered[2].wait(3)
        assert (
            domain.worker.ledger.settle_call(
                blocker["call_id"],
                blocker["execution_instance_id"],
                usage={"input_tokens": 3, "output_tokens": 4},
                quiesced=True,
                evidence="wrapper_thread_exited",
            )
            is False
        )
        gate = client.get(URL + "/" + second["review_id"]).json()["dispatch_gate"]
        assert gate["blocked_by"][0]["call_id"] != blocker["call_id"]
        assert not gate["can_claim"]
        release_second.set()
        assert (
            wait_status(client, second["review_id"], {"completed_degraded", "failed"})["status"]
            == "completed_degraded"
        )
        with domain.store.read() as conn:
            call = domain.store.row(
                conn,
                "SELECT status,body FROM contract_review_calls WHERE id=:id",
                id=blocker["call_id"],
            )
            raw = json.loads(call["body"])
            assert call["status"] == "UNKNOWN"
            assert raw["result"] is None and raw["acceptance"] is None
            assert raw["usage"] == {"input_tokens": 3, "output_tokens": 4}
            assert raw["local_io_state"] == "quiesced"
        assert client.get(URL + "/" + first["review_id"]).json()["budget"]["model_calls"] == 1


def test_failed_intent_persistence_dispatches_zero_requests(
    running_app, monkeypatch, controlled_adapter
):
    adapter = controlled_adapter()
    with running_app(adapter) as (client, domain, body):
        original = domain.store.event

        def fail_intent(conn, review, input_id, job, kind, payload, **links):
            if kind == "dispatch_intent":
                raise ReviewError("EVIDENCE_PERSISTENCE_FAILED", "Injected failure", 503)
            return original(conn, review, input_id, job, kind, payload, **links)

        monkeypatch.setattr(domain.store, "event", fail_intent)
        accepted = submit(client, body, "one")
        failed = wait_status(client, accepted["review_id"], {"failed"})
        assert failed["error_code"] == "EVIDENCE_PERSISTENCE_FAILED"
        assert adapter.requests == []
        assert failed["budget"]["model_calls"] == 0


def test_fixed_review_gets_one_rework_then_fails(running_app, controlled_adapter):
    adapter = controlled_adapter(reject_review=True)
    with running_app(adapter) as (client, _, body):
        accepted = submit(client, body, "one")
        failed = wait_status(client, accepted["review_id"], {"failed"})
        assert failed["error_code"] == "REPORT_REVIEW_FAILED"
        assert len(adapter.requests) == 4
        assert "revision_feedback" in json.loads(adapter.requests[2]["messages"][1]["content"])


def test_restart_interrupts_running_preserves_queued_and_fences_old_host(review_client):
    client, domain, body = review_client
    first = submit(client, body, "first")
    second = submit(client, body, "second")
    old = ExecutionLedger(domain)
    old.start()
    active = old.claim()
    current = ExecutionLedger(domain)
    current.start()
    assert client.get(URL + "/" + first["review_id"]).json()["job_status"] == "interrupted"
    assert current.claim()["job_id"] == second["job_id"]
    with domain.store.transaction() as conn, pytest.raises(ReviewError, match="执行权"):
        old.fence(conn, active)


@pytest.mark.parametrize("fail_commit", [False, True])
def test_revision_switch_clears_current_report_atomically_and_preserves_history(
    running_app, monkeypatch, fail_commit, controlled_adapter
):
    adapter = controlled_adapter()
    with running_app(adapter) as (client, domain, body):
        first = submit(client, body, "first")
        old_status = wait_status(client, first["review_id"], {"completed_degraded"})
        old_report_id = old_status["current_report_revision_id"]
        domain.worker.close()
        with domain.store.read() as conn:
            frozen = json.loads(
                domain.store.row(
                    conn,
                    "SELECT body FROM contract_review_inputs WHERE id=:id",
                    id=first["input_revision_id"],
                )["body"]
            )
        frozen["input_revision_id"] = identity("ir")
        frozen["original_request"]["request"] += "明确的新一轮说明。"
        for adoption in frozen["adoption_records"]:
            adoption["input_revision_id"] = frozen["input_revision_id"]
        frozen.pop("input_hash")
        frozen["input_hash"] = digest(frozen)
        if fail_commit:
            original = domain.store.event

            def fail(conn, review, input_id, job, kind, payload, **links):
                if kind == "input_revised":
                    raise ReviewError("EVIDENCE_PERSISTENCE_FAILED", "Injected failure", 503)
                return original(conn, review, input_id, job, kind, payload, **links)

            monkeypatch.setattr(domain.store, "event", fail)
            with pytest.raises(ReviewError), domain.store.transaction() as conn:
                domain.enqueue_revision(conn, first["review_id"], old_status["version"], frozen)
            current = client.get(URL + "/" + first["review_id"]).json()
            assert current["current_report_revision_id"] == old_report_id
            assert current["current_input_revision_id"] == first["input_revision_id"]
        else:
            with domain.store.transaction() as conn:
                domain.enqueue_revision(conn, first["review_id"], old_status["version"], frozen)
            current = client.get(URL + "/" + first["review_id"]).json()
            assert current["status"] == "queued"
            assert current["current_report_revision_id"] is None
            assert current["budget"]["model_calls"] == 2
            assert client.get(URL + "/" + first["review_id"] + "/report").status_code == 404
            context = domain.worker.ledger.claim()
            domain.worker.ledger.fail(context, "INJECTED_NEW_INPUT_FAILURE", elapsed=0)
            assert client.get(URL + "/" + first["review_id"]).json()["report_available"] is False
        historical = client.get(
            URL + "/" + first["review_id"] + "/report", params={"report_revision_id": old_report_id}
        ).json()
        assert historical["input_revision_id"] == first["input_revision_id"]


def test_partial_unknown_usage_is_independent_of_local_slot_and_settlement_is_idempotent(
    review_client,
):
    client, domain, body = review_client
    accepted = submit(client, body, "first")
    ledger = ExecutionLedger(domain)
    ledger.start()
    context = ledger.claim()
    profile = context["frozen"]["execution_profile"]
    payload = {
        "model": profile["model"],
        "max_tokens": profile["max_output_tokens"],
        "messages": [{"role": "user", "content": "controlled request"}],
    }
    call_id, instance = ledger.reserve_call(context, "analysis", payload, [])
    assert ledger.settle_call(call_id, instance, usage={"input_tokens": 0, "output_tokens": True})
    with domain.store.read() as conn:
        assert ledger.owner(conn)["slot_call_id"] == call_id
        account = ledger.account(conn, accepted["review_id"])
        assert account["usage_status"] == "partial"
        assert account["input_tokens"] == 0 and account["output_tokens"] is None
        assert account["token_ledger"]["output_tokens"]["reserved"] == profile["max_output_tokens"]
    assert ledger.settle_call(call_id, instance, usage={"input_tokens": 0}) is False
    assert ledger.settle_call(call_id, instance, usage={"input_tokens": 7})
    with domain.store.read() as conn:
        assert ledger.account(conn, accepted["review_id"])["input_tokens"] == 0
    assert ledger.settle_call(call_id, instance, quiesced=True, evidence="wrapper_thread_exited")
    with domain.store.read() as conn:
        assert ledger.owner(conn)["slot_call_id"] is None
        assert ledger.account(conn, accepted["review_id"])["output_tokens"] is None


@pytest.mark.parametrize("phase", ["analysis_reason", "review_subject"])
def test_worker_rejects_foreign_action_material_or_fixed_review_subject(
    running_app, controlled_adapter, phase
):
    adapter = controlled_adapter(reject_review=phase == "review_subject")
    original = adapter.complete

    def bad_reference(payload):
        result = original(payload)
        body = json.loads(result["content"])
        if phase == "analysis_reason":
            body["reason"]["evidence_refs"] = [{"kind": "rule", "adoption_id": "another-input"}]
        elif body.get("type") == "review_result":
            body["issues"][0].update(subject_kind="finding", subject_id="another-report")
        result["content"] = json.dumps(body, ensure_ascii=False)
        return result

    adapter.complete = bad_reference
    with running_app(adapter) as (client, domain, request):
        accepted = submit(client, request, "one")
        failed = wait_status(client, accepted["review_id"], {"failed"})
        assert failed["error_code"] == (
            "ACTION_PROTOCOL_ERROR" if phase == "analysis_reason" else "REPORT_REVIEW_FAILED"
        )
        assert not failed["report_available"]
        with domain.store.read() as conn:
            rows = conn.exec_driver_sql(
                "SELECT status FROM contract_review_calls ORDER BY rowid"
            ).all()
            assert rows[-1].status == "rejected"
