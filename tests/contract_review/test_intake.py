"""Atomic intake, stable replay and authenticated evidence queries."""

import copy
import json

import pytest
from sqlalchemy import text

from specflow.contract_review.common import ReviewError
from specflow.contract_review.service import ReviewService

URL = "/api/v1/contract-reviews"


def create(client, body, key="create-one"):
    return client.post(URL, json=body, headers={"Idempotency-Key": key})


def test_accepted_input_is_durable_and_replay_returns_original_response(review_client):
    client, domain, body = review_client
    first = create(client, body)
    assert first.status_code == 202, first.text
    accepted = first.json()
    review_id = accepted["review_id"]
    status = client.get(URL + "/" + review_id).json()
    assert status["status"] == "queued"
    assert status["report_available"] is False
    assert len(status["check_manifest"]) == 2
    assert status["execution_profile"]["execution_mode"] == "test"
    assert status["dispatch_gate"]["reason_codes"] == ["runtime_not_ready"]
    assert (
        client.get(URL + "/" + review_id + "/report").json()["error"]["code"]
        == "REPORT_NOT_AVAILABLE"
    )
    with domain.store.read() as conn:
        row = domain.store.row(
            conn,
            "SELECT body FROM contract_review_inputs WHERE id=:id",
            id=accepted["input_revision_id"],
        )
        assert json.loads(row["body"])["original_request"] == body
        assert (
            domain.store.row(conn, "SELECT count(*) AS n FROM contract_review_source_blobs")["n"]
            == 4
        )
    assert create(client, body).json() == accepted
    altered = copy.deepcopy(body)
    altered["request"] += "changed"
    assert create(client, altered).json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    with domain.store.read() as conn:
        assert domain.store.row(conn, "SELECT count(*) AS n FROM contract_reviews")["n"] == 1


def test_event_append_failure_rolls_back_entire_intake(review_client, monkeypatch):
    client, domain, body = review_client

    def fail(*args, **kwargs):
        raise ReviewError("STORAGE_CAPACITY_EXCEEDED", "Injected write failure", 503)

    monkeypatch.setattr(domain.store, "event", fail)
    assert create(client, body).status_code == 503
    with domain.store.read() as conn:
        for table in (
            "contract_reviews",
            "contract_review_inputs",
            "contract_review_snapshots",
            "contract_review_jobs",
            "contract_review_source_blobs",
            "contract_review_idempotency",
        ):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        assert (
            domain.store.row(conn, "SELECT * FROM contract_review_capacity WHERE id=1")[
                "snapshot_bytes"
            ]
            == 0
        )


def test_snapshot_capacity_and_invalid_authority_create_no_partial_review(review_client):
    client, domain, body = review_client
    domain.store.snapshot_capacity = 1
    assert create(client, body).json()["error"]["code"] == "STORAGE_CAPACITY_EXCEEDED"
    domain.store.snapshot_capacity = 1024**3
    body["authority_bindings"][0]["path"] = "missing.json"
    assert create(client, body).json()["error"]["code"] == "INVALID_AUTHORITY_BINDING"
    with domain.store.read() as conn:
        assert domain.store.row(conn, "SELECT count(*) AS n FROM contract_reviews")["n"] == 0


def test_event_body_is_available_only_under_correct_review(review_client):
    client, _, body = review_client
    first, second = create(client, body).json(), create(client, body, "second").json()
    base = URL + "/" + first["review_id"]
    events = client.get(base + "/events").json()
    assert events["next_cursor"] is None
    event_id = events["items"][0]["event_id"]
    assert client.get(base + "/events/" + event_id).json()["payload"] == first
    wrong = client.get(URL + "/" + second["review_id"] + "/events/" + event_id)
    assert wrong.status_code == 404
    assert client.get(base + "/events", params={"job_id": second["job_id"]}).status_code == 404
    assert client.get(base, params={"unknown": "value"}).status_code == 422
    assert client.get(base + "/events", params={"cursor": "not-a-cursor"}).status_code == 422
    client.headers.pop("X-API-Key")
    assert client.get(base + "/events/" + event_id).status_code == 401


def test_oversized_request_and_disabled_profile_do_not_create_rows(review_client):
    client, domain, body = review_client
    response = client.post(URL, content=b"x" * (1024**2 + 1), headers={"Idempotency-Key": "large"})
    assert response.status_code == 413
    domain.profiles.clear()
    assert create(client, body).json()["error"]["code"] == "RETRY_PROFILE_UNAVAILABLE"
    with domain.store.read() as conn:
        assert domain.store.row(conn, "SELECT count(*) AS n FROM contract_reviews")["n"] == 0


def test_profile_does_not_accept_or_echo_credentials_or_unselected_options(review_client):
    _, domain, _ = review_client
    profiles = copy.deepcopy(domain.profiles)
    profile = next(iter(profiles.values()))
    profile["api_key"] = "synthetic-credential-sentinel"
    with pytest.raises(RuntimeError) as caught:
        ReviewService(domain.store, domain.snapshot_reader, profiles)
    assert "synthetic-credential-sentinel" not in str(caught.value)
    del profile["api_key"]
    profile["options"]["write"] = True
    with pytest.raises(RuntimeError):
        ReviewService(domain.store, domain.snapshot_reader, profiles)
