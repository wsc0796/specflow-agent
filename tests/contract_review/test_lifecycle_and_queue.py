"""Controlled-adapter lifecycle evidence, never business-semantic acceptance."""

import copy
import json
import threading
import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity
from specflow.contract_review.common import ReviewError, digest, identity
from specflow.contract_review.execution import ExecutionLedger
from specflow.db import Project
from specflow.main import create_app

URL = "/api/v1/contract-reviews"


class ControlledAdapter:
    execution_mode = "test"

    def __init__(self, pauses=None, reject_review=False):
        self.requests = []
        self.pauses = pauses or {}
        self.entered = {index: threading.Event() for index in self.pauses}
        self.reject_review = reject_review
        self.before_response = None

    def complete(self, payload):
        self.requests.append(copy.deepcopy(payload))
        count = len(self.requests)
        if self.before_response:
            self.before_response(count)
        if count in self.pauses:
            self.entered[count].set()
            assert self.pauses[count].wait(8), "Test did not release the controlled call"
        data = json.loads(payload["messages"][1]["content"])
        if "candidate_report" in data:
            result = {
                "schema_version": "contract-review-review-result.v2",
                "type": "review_result",
                "candidate_report_hash": data["candidate_report_hash"],
                "outcome": "revise" if self.reject_review else "accept",
                "issues": (
                    [
                        {
                            "subject_kind": "report",
                            "subject_id": "",
                            "code": "other",
                            "reason": "受控返工场景",
                            "evidence_refs": [],
                        }
                    ]
                    if self.reject_review
                    else []
                ),
                "revision_feedback": "固定复核要求返工。" if self.reject_review else "",
            }
        else:
            missing = "受控替身仅验证程序链，不提供业务语义判断。"
            findings = [
                {
                    "id": "f" + str(index),
                    "target_ids": [target["target_id"]],
                    "judgment_status": "insufficient_evidence",
                    "affected_artifacts": ["documentation"],
                    "labels": [],
                    "claim": missing,
                    "rule_refs": [],
                    "source_refs": [],
                    "observation_refs": [],
                    "verification_evidence_refs": [],
                    "execution_verification": "NOT_RUN",
                    "limitations": [missing],
                }
                for index, target in enumerate(data["targets"])
            ]
            target_to_finding = {finding["target_ids"][0]: finding["id"] for finding in findings}
            report = {
                "schema_version": "contract-review-report-payload.v2.1",
                "summary": missing,
                "coverage": [
                    {
                        "target_id": target["target_id"],
                        "status": "partial",
                        "source_refs": [],
                        "missing_information": [missing],
                    }
                    for target in data["targets"]
                ],
                "check_results": [
                    {
                        "check_id": check["check_id"],
                        "status": "not_checked",
                        "finding_ids": [target_to_finding[check["target_id"]]],
                        "source_refs": [],
                        "observation_refs": [],
                        "missing_information": [missing],
                    }
                    for check in data["check_manifest"]
                ],
                "rule_uses": [],
                "findings": findings,
                "questions": [],
                "work_items": [],
                "acceptance_items": [],
                "adopted_child_result_refs": [],
                "limitations": [missing],
            }
            result = {
                "schema_version": "contract-review-action.v2.1",
                "action": "submit_report",
                "reason": {
                    "gap": "验证程序提交",
                    "evidence_refs": [],
                    "expected_information": "保存受控报告",
                },
                "report": report,
            }
        return {
            "content": json.dumps(result, ensure_ascii=False),
            "model": payload["model"],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }


@pytest.fixture
def running_app(tmp_path, git_repo, test_profile):
    root, _, request = git_repo

    @contextmanager
    def start(adapter, timeout=1.0):
        fast = {**test_profile, "model_timeout_seconds": timeout}
        slow = {**test_profile, "profile_id": "slow-test", "model_timeout_seconds": 5.0}
        app = create_app(
            f"sqlite:///{(tmp_path / 'worker.sqlite').as_posix()}",
            tmp_path / "artifacts",
            ApiSecurity(api_key="test-key", allowed_repository_roots=(str(tmp_path),)),
            contract_review_profiles={fast["profile_id"]: fast, slow["profile_id"]: slow},
            contract_review_adapter=adapter,
        )
        with TestClient(app) as client:
            with app.state.database.factory() as session:
                session.add(Project(id="project-test", name="Fixture", repository_path=str(root)))
                session.commit()
            client.headers["X-API-Key"] = "test-key"
            body = {**request, "execution_profile_id": fast["profile_id"]}
            try:
                yield client, app.state.contract_reviews, body
            finally:
                for event in adapter.pauses.values():
                    event.set()

    return start


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


def test_intake_to_report_persists_calls_before_actual_adapter_and_returns_quality(running_app):
    adapter = ControlledAdapter()
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


def test_timeout_holds_slot_then_late_cleanup_resumes_queue_without_accepting_old_body(running_app):
    release_first, release_second = threading.Event(), threading.Event()
    adapter = ControlledAdapter({1: release_first, 2: release_second})
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


def test_failed_intent_persistence_dispatches_zero_requests(running_app, monkeypatch):
    adapter = ControlledAdapter()
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


def test_fixed_review_gets_one_rework_then_fails(running_app):
    adapter = ControlledAdapter(reject_review=True)
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
    running_app, monkeypatch, fail_commit
):
    adapter = ControlledAdapter()
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
