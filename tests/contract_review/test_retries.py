"""Same-input retry admission, isolated from live providers and model semantics."""

import copy
import json
import threading

import pytest
from test_checkpoints import HumanAdapter, answer, batch, post, waiting
from test_lifecycle_and_queue import submit, wait_status

from specflow.contract_review.common import ReviewError
from specflow.contract_review.execution import ExecutionLedger
from specflow.contract_review.shared_ledger import SharedLedger

URL = "/api/v1/contract-reviews"


def failed_review(review_client):
    client, domain, body = review_client
    accepted = submit(client, body, "source")
    ledger = ExecutionLedger(domain)
    ledger.start()
    context = ledger.claim()
    ledger.fail(context, "INJECTED_FAILURE", elapsed=0)
    state = client.get(URL + "/" + accepted["review_id"]).json()
    request = {
        "expected_version": state["version"],
        "failed_job_id": accepted["job_id"],
        "input_revision_id": accepted["input_revision_id"],
        "reason": "显式重试同一冻结输入。",
        "mode": "fresh",
    }
    return client, domain, accepted, state, request


def post_retry(client, accepted, request, key="retry"):
    return client.post(
        URL + "/" + accepted["review_id"] + "/retries",
        json=request,
        headers={"Idempotency-Key": key},
    )


def counts(domain):
    with domain.store.read() as conn:
        return tuple(
            conn.exec_driver_sql("SELECT count(*) FROM " + table).scalar_one()
            for table in (
                "contract_review_inputs",
                "contract_review_jobs",
                "contract_review_events",
                "contract_review_idempotency",
            )
        )


def test_fresh_retry_is_atomic_same_input_and_success_replay_precedes_cas(review_client):
    client, domain, accepted, state, request = failed_review(review_client)
    before = counts(domain)
    response = post_retry(client, accepted, request)
    assert response.status_code == 202, response.text
    retried = response.json()
    assert retried["job_id"] != accepted["job_id"]
    assert retried["input_revision_id"] == accepted["input_revision_id"]
    assert retried["retry_of_job_id"] == accepted["job_id"]
    assert retried["attempt_no"] == 2
    after = counts(domain)
    assert after[0] == before[0] and after[1] == before[1] + 1
    assert post_retry(client, accepted, request).json() == retried
    assert counts(domain) == after
    current = client.get(URL + "/" + accepted["review_id"]).json()
    assert current["status"] == "queued" and not current["report_available"]
    assert current["input_hash"] == state["input_hash"]
    assert current["execution_profile"] == state["execution_profile"]
    assert current["budget"] == state["budget"]
    assert current["recovery"]["requested_mode"] == "fresh"
    different = {**request, "mode": "reuse_completed", "recovery_fallback": "stop"}
    assert (
        post_retry(client, accepted, different).json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    )


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"expected_version": 1}, "VERSION_CONFLICT"),
        ({"input_revision_id": "ir_other"}, "RETRY_TARGET_NOT_CURRENT"),
        ({"failed_job_id": "job_other"}, "RETRY_TARGET_NOT_CURRENT"),
        ({"mode": "reuse_completed", "recovery_fallback": "stop"}, "OPTION_NOT_ENABLED"),
    ],
)
def test_rejected_retry_preserves_every_record(review_client, patch, code):
    client, domain, accepted, _, request = failed_review(review_client)
    before = counts(domain)
    response = post_retry(client, accepted, {**request, **patch})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == code
    assert counts(domain) == before


@pytest.mark.parametrize(
    "patch",
    [
        {"mode": "fresh", "recovery_fallback": "stop"},
        {"mode": "reuse_completed"},
        {"mode": "resume_anywhere"},
        {"expected_version": True},
        {"recovery_fallback": None},
        {"model": "override"},
    ],
)
def test_retry_request_is_strict(review_client, patch):
    client, domain, accepted, _, request = failed_review(review_client)
    before = counts(domain)
    response = post_retry(client, accepted, {**request, **patch})
    assert response.status_code == 422, response.text
    assert counts(domain) == before


def test_retry_storage_failure_rolls_back_job_cas_budget_and_idempotency(
    review_client, monkeypatch
):
    client, domain, accepted, state, request = failed_review(review_client)
    before = counts(domain)
    original = domain.store.event

    def fail(conn, review, input_id, job, kind, payload, **links):
        if kind == "retry_queued":
            raise ReviewError("EVIDENCE_PERSISTENCE_FAILED", "Injected storage fault", 503)
        return original(conn, review, input_id, job, kind, payload, **links)

    monkeypatch.setattr(domain.store, "event", fail)
    response = post_retry(client, accepted, request)
    assert response.status_code == 503
    assert counts(domain) == before
    current = client.get(URL + "/" + accepted["review_id"]).json()
    assert current["version"] == state["version"]
    assert current["job_id"] == state["job_id"] and current["budget"] == state["budget"]


def test_retry_refuses_profile_drift_without_fallback_replacement(review_client):
    client, domain, accepted, state, request = failed_review(review_client)
    profile_id = state["execution_profile"]["profile_id"]
    updated = copy.deepcopy(domain.profiles[profile_id])
    updated["analysis_prompt"] += " new deployment"
    domain.profiles[profile_id] = updated
    before = counts(domain)
    response = post_retry(client, accepted, request)
    assert response.json()["error"]["code"] == "RETRY_PROFILE_UNAVAILABLE"
    assert counts(domain) == before


def test_completed_review_cannot_use_failure_retry(running_app, controlled_adapter):
    with running_app(controlled_adapter()) as (client, _, body):
        accepted = submit(client, body, "completed")
        state = wait_status(client, accepted["review_id"], {"completed_degraded"})
        request = {
            "expected_version": state["version"],
            "failed_job_id": state["job_id"],
            "input_revision_id": state["current_input_revision_id"],
            "reason": "不能把重新生成冒充失败重试。",
            "mode": "fresh",
        }
        assert post_retry(client, accepted, request).json()["error"]["code"] == "RETRY_NOT_ALLOWED"


def test_retry_cannot_reset_exhausted_review_budget(review_client):
    client, domain, accepted, _, request = failed_review(review_client)
    with domain.store.transaction() as conn:
        row = domain.store.row(
            conn,
            "SELECT body FROM contract_review_budget_accounts WHERE review_id=:id",
            id=accepted["review_id"],
        )
        account = json.loads(row["body"])
        account["model_calls"] = account["grant"]["model_calls"]
        domain.store.execute(
            conn,
            "UPDATE contract_review_budget_accounts SET body=:body WHERE review_id=:id",
            id=accepted["review_id"],
            body=json.dumps(account),
        )
    before = counts(domain)
    response = post_retry(client, accepted, request)
    assert response.json()["error"]["code"] == "REVIEW_BUDGET_EXHAUSTED"
    assert counts(domain) == before


def test_retry_is_authenticated_and_rejects_undefined_query(review_client):
    client, domain, accepted, _, request = failed_review(review_client)
    path = URL + "/" + accepted["review_id"] + "/retries"
    before = counts(domain)
    assert (
        client.post(
            path, json=request, headers={"X-API-Key": "wrong", "Idempotency-Key": "auth"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            path + "?resume_at=2", json=request, headers={"Idempotency-Key": "query"}
        ).status_code
        == 422
    )
    assert counts(domain) == before


def test_retry_stays_queued_until_original_local_io_is_reliably_finished(
    running_app, controlled_adapter
):
    release = threading.Event()
    adapter = controlled_adapter({1: release})
    with running_app(adapter, timeout=0.1) as (client, domain, body):
        accepted = submit(client, body, "inflight")
        assert adapter.entered[1].wait(2)
        failed = wait_status(client, accepted["review_id"], {"failed"})
        assert failed["error_code"] == "CALL_RESULT_UNKNOWN"
        request = {
            "expected_version": failed["version"],
            "failed_job_id": failed["job_id"],
            "input_revision_id": failed["current_input_revision_id"],
            "reason": "未收尾时只允许排队，不新派发。",
            "mode": "fresh",
        }
        response = post_retry(client, accepted, request)
        assert response.status_code == 202, response.text
        queued = client.get(URL + "/" + accepted["review_id"]).json()
        assert queued["status"] == "queued" and not queued["dispatch_gate"]["can_claim"]
        assert len(adapter.requests) == 1
        release.set()
        final = wait_status(client, accepted["review_id"], {"completed_degraded", "failed"})
        assert final["status"] == "completed_degraded", final
        assert final["budget"]["model_calls"] == 3
        with domain.store.read() as conn:
            old = domain.store.row(
                conn, "SELECT body FROM contract_review_calls WHERE job_id=:id", id=failed["job_id"]
            )
            assert json.loads(old["body"])["result"] is None


def test_startup_preserves_waiting_report_and_partial_human_answers(
    running_app, controlled_adapter
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        partial = post(client, review_id, batch(state, report, [answer()]))
        assert partial.status_code == 200
        before = client.get(URL + "/" + review_id).json()
        domain.worker.close()
        domain.worker = None
        SharedLedger(domain).start()
        after = client.get(URL + "/" + review_id).json()
        assert after["status"] == "awaiting_decision"
        assert after["job_id"] == before["job_id"]
        assert after["current_input_revision_id"] == before["current_input_revision_id"]
        assert after["current_report_revision_id"] == before["current_report_revision_id"]
        assert after["resolutions"] == before["resolutions"]
        assert after["remaining_blocking_question_ids"] == before["remaining_blocking_question_ids"]
