"""External claims stay immutable and only explicit later adoption can use them."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from specflow.contract_review.common import ReviewError, identity

URL = "/api/v1/contract-reviews"


def wait_report(client, review_id):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        state = client.get(f"{URL}/{review_id}").json()
        if state["report_available"]:
            return state, client.get(f"{URL}/{review_id}/report").json()
        if state["status"] == "failed":
            pytest.fail(str(state))
        time.sleep(0.01)
    pytest.fail("Controlled report did not arrive")


def create(client, body, key="review"):
    response = client.post(URL, json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()["review_id"]


def evidence_body(state, report):
    return {
        "expected_version": state["version"],
        "input_revision_id": report["input_revision_id"],
        "report_revision_id": report["report_revision_id"],
        "finding_ids": [item["id"] for item in report["payload"]["findings"]],
        "kind": "external_controlled_execution",
        "environment": "隔离示例环境",
        "source_commit_sha": report["commit_sha"],
        "procedure": "提供者声明的操作步骤；系统不执行。",
        "observed_result": "提供者声称通过，但没有足够独立证据。",
        "evidence_text": "一条有界的提供者记录。",
        "actor_label": "自填维护者标签",
    }


@pytest.fixture
def completed_review(running_app, controlled_adapter):
    with running_app(controlled_adapter()) as (client, domain, body):
        review_id = create(client, body)
        state, report = wait_report(client, review_id)
        domain.worker.close()
        yield client, domain, review_id, state, report


def post(client, review_id, body, key="evidence"):
    return client.post(
        f"{URL}/{review_id}/verification-evidence", json=body, headers={"Idempotency-Key": key}
    )


def counts(domain, review_id):
    with domain.store.read() as conn:
        return tuple(
            domain.store.row(conn, query, id=review_id)["n"]
            for query in (
                "SELECT version AS n FROM contract_reviews WHERE id=:id",
                "SELECT count(*) AS n FROM contract_review_verification_evidence "
                "WHERE review_id=:id",
                "SELECT event_seq AS n FROM contract_reviews WHERE id=:id",
                "SELECT count(*) AS n FROM contract_review_jobs WHERE review_id=:id",
            )
        )


def next_input(domain, review_id, modify=None, selected=None):
    with domain.store.transaction() as conn:
        current = domain.require_review(conn, review_id)
        frozen = domain.verifications.input(conn, review_id, current["current_input_id"])
        frozen["input_revision_id"] = identity("ir")
        for rule in frozen["adoption_records"]:
            rule["input_revision_id"] = frozen["input_revision_id"]
        if modify:
            modify(frozen)
        return domain.enqueue_revision(conn, review_id, current["version"], frozen, selected)


def test_weak_claim_is_saved_but_not_adopted_executed_or_applied_to_old_report(completed_review):
    client, domain, review_id, state, report = completed_review
    before = counts(domain, review_id)
    body = evidence_body(state, report)
    response = post(client, review_id, body)
    assert response.status_code == 201, response.text
    accepted = response.json()
    assert accepted["status"] == "provided_not_independently_verified"
    assert counts(domain, review_id) == (before[0] + 1, 1, before[2] + 1, before[3])
    record = client.get(f"{URL}/{review_id}/verification-evidence/{accepted['evidence_id']}").json()
    assert record["evidence_text"] == body["evidence_text"]
    assert record["provider"]["actor_label"] == body["actor_label"]
    assert record["current_adoption"] is None
    assert record["current_applicability"] is None
    assert record["applicable_to_current_input"] is None
    assert record["origin"]["input_revision_id"] == report["input_revision_id"]
    assert client.get(f"{URL}/{review_id}/report").json() == report
    assert all(f["execution_verification"] == "NOT_RUN" for f in report["payload"]["findings"])
    assert post(client, review_id, body).json() == accepted
    assert counts(domain, review_id) == (before[0] + 1, 1, before[2] + 1, before[3])
    changed = {**body, "observed_result": "另一条声明"}
    assert post(client, review_id, changed).json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.parametrize(
    "bad", ["missing", "unknown", "bool_version", "empty", "utf8_bytes", "duplicate", "null"]
)
def test_schema_failure_is_422_detail_and_has_no_persistent_effect(completed_review, bad):
    client, domain, review_id, state, report = completed_review
    body = evidence_body(state, report)
    if bad == "missing":
        del body["evidence_text"]
    elif bad == "unknown":
        body["actor_subject"] = "forged-owner"
    elif bad == "bool_version":
        body["expected_version"] = True
    elif bad == "empty":
        body["evidence_text"] = " \n "
    elif bad == "utf8_bytes":
        body["evidence_text"] = "证" * (256 * 1024 // 3 + 1)
    elif bad == "duplicate":
        body["finding_ids"] *= 2
    else:
        body["related_findings"] = None
    before = counts(domain, review_id)
    response = post(client, review_id, body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert counts(domain, review_id) == before


@pytest.mark.parametrize(
    ("bad", "code", "status"),
    [
        ("finding", "RESOURCE_NOT_FOUND", 404),
        ("input", "RESOURCE_NOT_FOUND", 404),
        ("report", "RESOURCE_NOT_FOUND", 404),
        ("related", "RESOURCE_NOT_FOUND", 404),
        ("version", "VERSION_CONFLICT", 409),
        ("commit", "VERIFICATION_BASELINE_MISMATCH", 409),
    ],
)
def test_invalid_import_rejects_without_rows_or_version_changes(
    completed_review, bad, code, status
):
    client, domain, review_id, state, report = completed_review
    body = evidence_body(state, report)
    if bad == "finding":
        body["finding_ids"] = ["unknown"]
        body["expected_version"] = 1  # ownership wins over stale version
    elif bad == "input":
        body["input_revision_id"] = "unknown"
    elif bad == "report":
        body["report_revision_id"] = "unknown"
    elif bad == "related":
        body["related_findings"] = [
            {"report_revision_id": report["report_revision_id"], "finding_id": "unknown"}
        ]
    elif bad == "version":
        body["expected_version"] -= 1
        body["source_commit_sha"] = "0" * 40  # version wins over baseline
    else:
        body["source_commit_sha"] = "0" * 40
    before = counts(domain, review_id)
    response = post(client, review_id, body)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert counts(domain, review_id) == before


def test_historical_target_conflict_and_successful_replay_have_distinct_precedence(
    completed_review,
):
    client, domain, review_id, state, report = completed_review
    body = evidence_body(state, report)
    original_response = post(client, review_id, body).json()
    revised = next_input(domain, review_id, selected=[])
    assert post(client, review_id, body).json() == original_response
    historical = {**body, "expected_version": revised["version"], "source_commit_sha": "0" * 40}
    before = counts(domain, review_id)
    rejected = post(client, review_id, historical, "new-key")
    assert rejected.json()["error"]["code"] == "VERIFICATION_TARGET_NOT_CURRENT"
    assert counts(domain, review_id) == before


def test_failed_final_event_rolls_back_evidence_version_capacity_and_idempotency(
    completed_review, monkeypatch
):
    client, domain, review_id, state, report = completed_review
    body = evidence_body(state, report)
    original = domain.store.event

    def fail(conn, review, input_id, job, kind, payload, **links):
        if kind == "verification_evidence_imported":
            raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "Injected failure", 503)
        return original(conn, review, input_id, job, kind, payload, **links)

    before = counts(domain, review_id)
    with domain.store.read() as conn:
        capacity = dict(domain.store.row(conn, "SELECT * FROM contract_review_capacity"))
    monkeypatch.setattr(domain.store, "event", fail)
    assert post(client, review_id, body).status_code == 503
    assert counts(domain, review_id) == before
    with domain.store.read() as conn:
        assert dict(domain.store.row(conn, "SELECT * FROM contract_review_capacity")) == capacity
    monkeypatch.setattr(domain.store, "event", original)
    assert post(client, review_id, body).status_code == 201


@pytest.mark.parametrize(
    ("change", "summary", "expected"),
    [
        ("same", True, {"applicable"}),
        ("target", True, {"applicable", "inapplicable"}),
        ("purpose", None, {"unresolved"}),
        ("rule_purpose", None, {"unresolved"}),
        ("check_selector", True, {"applicable", "unresolved"}),
        ("missing_dimension", True, {"applicable", "unresolved"}),
        ("baseline", False, {"inapplicable"}),
    ],
)
def test_explicit_adoption_rechecks_each_target_without_rebinding_origin(
    completed_review, change, summary, expected
):
    client, domain, review_id, state, report = completed_review
    imported = post(client, review_id, evidence_body(state, report)).json()
    evidence_id = imported["evidence_id"]
    endpoint = f"{URL}/{review_id}/verification-evidence/{evidence_id}"
    original_record = client.get(endpoint).json()

    def modify(frozen):
        if change == "target":
            frozen["target_manifest"][0]["endpoint"]["path"] = "/different"
        elif change == "purpose":
            frozen["original_request"]["request"] += "Changed use of evidence."
        elif change == "rule_purpose":
            for adoption in frozen["adoption_records"]:
                adoption["provenance"]["purpose"] += "改变规则采用用途。"
        elif change == "check_selector":
            frozen["original_request"]["targets"][0]["checks"][0]["rule_selectors"] = [
                {
                    "path": "contracts/v2.json",
                    "selector": {"kind": "json_pointer", "pointer": "/endpoints/0"},
                }
            ]
        elif change == "missing_dimension":
            del frozen["target_manifest"][0]["source_path"]
        elif change == "baseline":
            frozen["commit_sha"] = "0" * 40

    revised = next_input(domain, review_id, modify, [evidence_id])
    before = counts(domain, review_id)
    current = client.get(endpoint).json()
    assert current["origin"] == original_record["origin"]
    assert current["body_hash"] == original_record["body_hash"]
    assert current["status"] == "provided_not_independently_verified"
    assert current["current_adoption"]["adopting_input_revision_id"] == revised["input_revision_id"]
    assert current["applicable_to_current_input"] is summary
    assert {item["applicability"] for item in current["current_applicability"]} == expected
    assert counts(domain, review_id) == before
    assert (
        client.get(
            f"{URL}/{review_id}/report", params={"report_revision_id": report["report_revision_id"]}
        ).json()
        == report
    )


def test_pagination_filters_ownership_and_authentication(completed_review):
    client, domain, review_id, state, report = completed_review
    identifiers = []
    for index in range(3):
        state = client.get(f"{URL}/{review_id}").json()
        identifiers.append(
            post(client, review_id, evidence_body(state, report), f"ev-{index}").json()[
                "evidence_id"
            ]
        )
    endpoint = f"{URL}/{review_id}/verification-evidence"
    before = counts(domain, review_id)
    first = client.get(endpoint, params={"limit": 1}).json()
    assert first["next_cursor"]
    second = client.get(endpoint, params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert second["next_cursor"] is None
    assert {item["evidence_id"] for item in first["items"] + second["items"]} == set(identifiers)
    assert (
        client.get(
            endpoint,
            params={
                "cursor": first["next_cursor"],
                "input_revision_id": report["input_revision_id"],
            },
        ).json()["error"]["code"]
        == "INVALID_CURSOR"
    )
    assert client.get(endpoint, params={"cursor": "broken"}).status_code == 422
    assert client.get(endpoint, params={"unknown": "value"}).status_code == 422
    assert counts(domain, review_id) == before
    client.headers.pop("X-API-Key")
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint + "/" + identifiers[0]).status_code == 401
    assert post(client, review_id, evidence_body(state, report), "unauthorized").status_code == 401


def test_cross_review_references_are_rejected_and_import_does_not_run_procedure(
    running_app, controlled_adapter, tmp_path
):
    with running_app(controlled_adapter()) as (client, domain, body):
        first, second = create(client, body, "a"), create(client, body, "b")
        state_a, report_a = wait_report(client, first)
        state_b, report_b = wait_report(client, second)
        imported = post(client, first, evidence_body(state_a, report_a)).json()
        evidence_id = imported["evidence_id"]
        assert client.get(f"{URL}/{second}/verification-evidence/{evidence_id}").status_code == 404
        assert post(client, second, evidence_body(state_a, report_a)).status_code == 404
        bad_history = evidence_body(state_b, report_b)
        bad_history["related_findings"] = [
            {
                "report_revision_id": report_a["report_revision_id"],
                "finding_id": report_a["payload"]["findings"][0]["id"],
            }
        ]
        assert post(client, second, bad_history).status_code == 404
        sentinel = tmp_path / "must-not-exist.txt"
        valid = evidence_body(state_b, report_b)
        valid["procedure"] = f"Create file at {sentinel}"
        assert post(client, second, valid).status_code == 201
        assert not sentinel.exists()
        domain.worker.close()
        with pytest.raises(ReviewError), domain.store.transaction() as conn:
            review = domain.require_review(conn, second)
            frozen = domain.verifications.input(conn, second, review["current_input_id"])
            domain.verifications.adopt(conn, second, frozen, [evidence_id])


def test_selected_evidence_body_reaches_next_actual_request_and_report_summary(
    running_app, controlled_adapter
):
    adapter = controlled_adapter()
    with running_app(adapter) as (client, domain, body):
        review_id = create(client, body)
        state, report = wait_report(client, review_id)
        imported = post(client, review_id, evidence_body(state, report)).json()
        evidence_id = imported["evidence_id"]
        assert len(adapter.requests) == 2
        assert "verification_evidence" not in json.loads(
            adapter.requests[0]["messages"][1]["content"]
        )
        revised = next_input(domain, review_id, selected=[evidence_id])
        _, new_report = wait_report(client, review_id)
        assert new_report["input_revision_id"] == revised["input_revision_id"]
        request = json.loads(adapter.requests[2]["messages"][1]["content"])
        assert request["verification_evidence"][0]["evidence_id"] == evidence_id
        assert request["verification_evidence"][0]["evidence_text"] == "一条有界的提供者记录。"
        assert new_report["verification_mode"] == "static_only"
        summary = new_report["verification_evidence_summary"][0]
        assert summary["status"] == "provided_not_independently_verified"
        assert summary["origin"]["input_revision_id"] == report["input_revision_id"]
        assert (
            summary["current_adoption"]["adopting_input_revision_id"]
            == revised["input_revision_id"]
        )


def test_concurrent_different_keys_share_one_expected_version(completed_review):
    client, domain, review_id, state, report = completed_review
    body = evidence_body(state, report)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: post(client, review_id, body, key), ["one", "two"]))
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert (
        next(response for response in responses if response.status_code == 409).json()["error"][
            "code"
        ]
        == "VERSION_CONFLICT"
    )
    assert counts(domain, review_id)[:2] == (state["version"] + 1, 1)


def test_revision_inherits_only_selected_evidence_and_explicit_empty_removes_selection(
    running_app, controlled_adapter
):
    with running_app(controlled_adapter()) as (client, domain, body):
        review_id = create(client, body)
        state, report = wait_report(client, review_id)
        first = post(client, review_id, evidence_body(state, report), "first").json()["evidence_id"]
        next_input(domain, review_id, selected=[first])
        state, second_report = wait_report(client, review_id)
        second = post(client, review_id, evidence_body(state, second_report), "second").json()[
            "evidence_id"
        ]

        def change_request(frozen):
            frozen["original_request"]["request"] += "重新检查并沿用已选证据。"

        next_input(domain, review_id, modify=change_request)
        _, inherited_report = wait_report(client, review_id)
        assert [
            item["evidence_id"] for item in inherited_report["verification_evidence_summary"]
        ] == [first]
        assert (
            client.get(f"{URL}/{review_id}/verification-evidence/{second}").json()[
                "current_adoption"
            ]
            is None
        )
        next_input(domain, review_id, selected=[])
        _, cleared = wait_report(client, review_id)
        assert cleared["verification_evidence_summary"] == []
        assert (
            client.get(f"{URL}/{review_id}/verification-evidence/{first}").json()[
                "current_adoption"
            ]
            is None
        )
        assert len(client.get(f"{URL}/{review_id}/verification-evidence").json()["items"]) == 2


def test_selected_large_body_is_not_silently_dropped_to_fit_model_context(
    running_app, controlled_adapter
):
    adapter = controlled_adapter()
    with running_app(adapter) as (client, domain, body):
        review_id = create(client, body)
        state, report = wait_report(client, review_id)
        evidence = evidence_body(state, report)
        evidence["evidence_text"] = "x" * 25000
        response = post(client, review_id, evidence)
        assert response.status_code == 201
        next_input(domain, review_id, selected=[response.json()["evidence_id"]])
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            state = client.get(f"{URL}/{review_id}").json()
            if state["status"] == "failed":
                break
            time.sleep(0.01)
        assert state["status"] == "failed"
        assert state["error_code"] == "BUDGET_EXHAUSTED"
        assert state["report_available"] is False
        assert len(adapter.requests) == 2
