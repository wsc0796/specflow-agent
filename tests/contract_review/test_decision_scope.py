"""Project decisions require explicit publication and preserve exact versioned slices."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import TypeAdapter

from specflow.contract_review import decisions as decisions_module
from specflow.contract_review.common import ReviewError
from specflow.contract_review.decisions import DecisionRequest, scope_subset, scopes_intersect
from specflow.contract_review.schemas import CreateReview, ExecutionProfile
from specflow.contract_review.service import ReviewService
from specflow.db import Project

URL = "/api/v1/projects/project-test/contract-decisions"
REVIEWS = "/api/v1/contract-reviews"
CREATE = {"method": "POST", "path": "/exports"}
CANCEL = {"method": "POST", "path": "/exports/{job_id}/cancel"}


def scope(endpoints=None, paths=None, versions=None):
    result = {"api_versions": versions or ["v2"]}
    if endpoints is not None:
        result["endpoints"] = endpoints
    if paths is not None:
        result["source_paths"] = paths
    return result


def confirm(version=0, *, selected_scope=None, text="创建返回 job_id；仅 queued 可取消。"):
    return {
        "operation": "confirm",
        "expected_ruleset_version": version,
        "text": text,
        "scope": selected_scope or scope([CREATE, CANCEL]),
        "provenance": {"kind": "declared", "text": "维护者独立确认的项目决定。"},
        "actor_label": "自填标签",
    }


def publish(client, body, key=None, expected=201):
    response = client.post(
        URL,
        json=body,
        headers={"Idempotency-Key": key or "decision-" + str(body["expected_ruleset_version"])},
    )
    assert response.status_code == expected, response.text
    return response.json()


def remove(old, version=1, *, selected_scope=None, operation="supersede"):
    selected_scope = selected_scope or scope([CANCEL])
    value = {
        "operation": operation,
        "expected_ruleset_version": version,
        "provenance": {"kind": "declared", "text": "明确部分替代或撤回。"},
        "supersedes" if operation == "supersede" else "withdrawals": [
            {"project_decision_id": old, "effective_scope": selected_scope}
        ],
    }
    if operation == "supersede":
        value.update(text="取消必须满足新条件。", scope=selected_scope)
    else:
        value["reason"] = "本切片不再有效。"
    return value


@pytest.fixture
def memory_client(review_client):
    client, domain, body = review_client
    for name, profile in list(domain.profiles.items()):
        value = copy.deepcopy(profile)
        value["options"]["project_memory"] = True
        domain.profiles[name] = ExecutionProfile.model_validate(value).frozen()
    return client, domain, copy.deepcopy(body)


def snapshot_input(domain, input_id):
    with domain.store.read() as conn:
        return json.loads(
            domain.store.row(
                conn, "SELECT body FROM contract_review_inputs WHERE id=:id", id=input_id
            )["body"]
        )


def create(client, body, version=1, key="review"):
    response = client.post(
        REVIEWS,
        json={
            **body,
            "ruleset_usage": {"mode": "applicable_confirmed", "expected_ruleset_version": version},
        },
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    return response.json()


def project_adoptions(frozen):
    return [r for r in frozen["adoption_records"] if r["origin"]["kind"] == "project_decision"]


def footprint(domain):
    with domain.store.read() as conn:
        return {
            table: [tuple(row) for row in conn.exec_driver_sql("SELECT * FROM " + table)]
            for table in (
                "project_contract_rulesets",
                "project_contract_decisions",
                "contract_review_idempotency",
                "contract_review_capacity",
            )
        }


def test_disabled_option_never_reads_or_publishes_long_term_records(review_client):
    client, _, body = review_client
    assert client.get(URL).json()["error"]["code"] == "OPTION_NOT_ENABLED"
    assert publish(client, confirm(), expected=409)["error"]["code"] == "OPTION_NOT_ENABLED"
    body["ruleset_usage"] = {"mode": "applicable_confirmed", "expected_ruleset_version": 0}
    response = client.post(REVIEWS, json=body, headers={"Idempotency-Key": "disabled"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OPTION_NOT_ENABLED"


@pytest.mark.parametrize(
    "patch",
    [
        {"operation": "withdraw"},
        {"operation": "supersede"},
        {"operation": "anything"},
        {"expected_ruleset_version": True},
        {"expected_ruleset_version": -1},
        {"expected_ruleset_version": "0"},
        {"expected_ruleset_version": 2**63},
        {"text": ""},
        {"text": "a" * 16001},
        {"text": None},
        {"actor_subject": "admin"},
        {"supersedes_ids": ["old"]},
        {"scope": {"api_versions": [], "endpoints": [CREATE]}},
        {"scope": {"api_versions": ["v2"], "endpoints": []}},
        {"scope": {"api_versions": ["v2"], "source_paths": None}},
        {"scope": {"api_versions": ["v2"]}},
        {"provenance": {"kind": "declared", "text": "x", "claimed_approver": "admin"}},
        {
            "provenance": {
                "kind": "review_record",
                "review_id": "r",
                "report_revision_id": "rr",
                "resolution_ids": [],
                "source_refs": [],
                "text": "wrong branch",
            }
        },
        {"provenance": {"kind": "declared", "text": None}},
    ],
)
def test_publication_strict_union_and_bounds(memory_client, patch):
    client, domain, _ = memory_client
    before = footprint(domain)
    publish(client, {**confirm(), **patch}, expected=422)
    assert footprint(domain) == before


@pytest.mark.parametrize("operation", ["supersede", "withdraw"])
def test_effect_bounds_and_branch_fields_are_strict(memory_client, operation):
    client, _, _ = memory_client
    payload = remove("old", operation=operation)
    field = "supersedes" if operation == "supersede" else "withdrawals"
    for invalid in ([], payload[field] * 21, None):
        publish(client, {**payload, field: invalid}, expected=422)
    invalid = copy.deepcopy(payload)
    invalid[field][0].pop("effective_scope")
    publish(client, invalid, expected=422)
    publish(
        client, {**payload, "reason" if operation == "supersede" else "text": "wrong"}, expected=422
    )


def test_atomic_counter_replay_conflict_and_reconstruction(memory_client):
    client, domain, _ = memory_client
    payload = confirm()
    first = publish(client, payload, "same")
    assert first["actor_subject"] == "shared-service"
    assert first["actor_label"] == "自填标签"
    assert first["original_request"] == payload
    publish(client, confirm(1), "next")
    before = footprint(domain)
    assert publish(client, payload, "same") == first
    assert (
        publish(client, {**payload, "text": "changed"}, "same", 409)["error"]["code"]
        == "IDEMPOTENCY_KEY_REUSED"
    )
    assert publish(client, payload, "stale", 409)["error"]["code"] == "RULESET_VERSION_CONFLICT"
    assert footprint(domain) == before
    fresh = ReviewService(domain.store, domain.snapshot_reader, domain.profiles)
    assert fresh.decisions.list("project-test")["ruleset_version"] == 2
    assert fresh.decisions.list("project-test")["items"][0]["text"] == first["text"]


def test_concurrent_different_keys_have_one_cas_winner(memory_client):
    _, domain, _ = memory_client
    request = TypeAdapter(DecisionRequest).validate_python(confirm())

    def call(key):
        try:
            return domain.decisions.publish("project-test", request, key)[0]
        except ReviewError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(call, ("a", "b")))
    assert sorted(map(str, result)) == ["201", "RULESET_VERSION_CONFLICT"]
    assert len(domain.decisions.list("project-test")["items"]) == 1


def test_concurrent_same_key_returns_identical_record(memory_client):
    _, domain, _ = memory_client
    request = TypeAdapter(DecisionRequest).validate_python(confirm())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: domain.decisions.publish("project-test", request, "same"), range(2))
        )
    assert results[0] == results[1]
    assert len(domain.decisions.list("project-test")["items"]) == 1


@pytest.mark.parametrize("operation", ["supersede", "withdraw"])
def test_partial_removal_preserves_other_scope_and_historical_version(memory_client, operation):
    client, domain, body = memory_client
    old = publish(client, confirm())["project_decision_id"]
    historic = client.get(URL, params={"ruleset_version": 1}).json()
    new = publish(client, remove(old, operation=operation))
    assert client.get(URL, params={"ruleset_version": 1}).json() == historic
    body["targets"] = [
        {
            "api_version": "v2",
            "endpoint": endpoint,
            "checks": [{"key": "condition", "behavior": "核对条件"}],
        }
        for endpoint in (CREATE, CANCEL)
    ]
    result = create(client, body, 2)
    frozen = snapshot_input(domain, result["input_revision_id"])
    old_rows = [r for r in project_adoptions(frozen) if r["origin"]["project_decision_id"] == old]
    by_path = {r["matched_target"]["endpoint"]["path"]: r for r in old_rows}
    assert by_path[CREATE["path"]]["disposition"] == "adopted"
    cancelled = by_path[CANCEL["path"]]
    assert cancelled["disposition"] == "excluded"
    assert cancelled["reason_code"] == (
        "SUPERSEDED_SLICE" if operation == "supersede" else "WITHDRAWN_SLICE"
    )
    assert cancelled["body"] == historic["items"][0]["text"]
    assert cancelled["effect_relation_refs"] == [new["effect_relations"][0]["effect_relation_id"]]
    if operation == "supersede":
        assert any(
            r["disposition"] == "adopted"
            and r["origin"]["project_decision_id"] == new["project_decision_id"]
            for r in project_adoptions(frozen)
        )


@pytest.mark.parametrize(
    "slice_scope,new_scope",
    [
        (scope([CREATE], versions=["v1"]), scope([CREATE], versions=["v1"])),
        (scope([{"method": "GET", "path": "/unrelated"}]), scope([CREATE])),
        (scope([CREATE]), scope([CANCEL])),
        (scope(paths=["docs/a.md"]), scope([CREATE])),
    ],
)
def test_out_of_scope_and_empty_intersection_are_rejected(memory_client, slice_scope, new_scope):
    client, domain, _ = memory_client
    old = publish(client, confirm())["project_decision_id"]
    payload = remove(old, selected_scope=slice_scope)
    payload["scope"] = new_scope
    before = footprint(domain)
    assert publish(client, payload, expected=409)["error"]["code"] == "DECISION_SCOPE_CONFLICT"
    assert footprint(domain) == before


@pytest.mark.parametrize("operation", ["supersede", "withdraw"])
def test_already_removed_overlap_and_same_batch_overlap_roll_back(memory_client, operation):
    client, domain, _ = memory_client
    old = publish(client, confirm())["project_decision_id"]
    payload = remove(old, operation=operation)
    field = "supersedes" if operation == "supersede" else "withdrawals"
    duplicate = copy.deepcopy(payload)
    duplicate[field] *= 2
    before = footprint(domain)
    assert (
        publish(client, duplicate, "duplicate", 409)["error"]["code"] == "DECISION_SCOPE_CONFLICT"
    )
    assert footprint(domain) == before
    publish(client, payload)
    before = footprint(domain)
    # A request mixing valid create and invalid removed cancel is rejected whole.
    payload = remove(old, 2, selected_scope=scope([CREATE, CANCEL]), operation=operation)
    assert publish(client, payload, expected=409)["error"]["code"] == "DECISION_SCOPE_CONFLICT"
    assert footprint(domain) == before


@pytest.mark.parametrize("failure", ["capacity", "counter", "record", "idempotency"])
def test_publication_storage_failures_rollback_all_records(memory_client, monkeypatch, failure):
    _, domain, _ = memory_client
    before = footprint(domain)
    original = domain.store.execute

    def execute(conn, statement, **params):
        if (
            (failure == "counter" and statement.startswith("UPDATE project_contract_rulesets"))
            or (
                failure == "record"
                and statement.startswith("INSERT INTO project_contract_decisions")
            )
            or (
                failure == "idempotency"
                and statement.startswith("INSERT INTO contract_review_idempotency")
            )
        ):
            raise ReviewError("DEPENDENCY_UNAVAILABLE", "受控存储失败。", 503)
        return original(conn, statement, **params)

    monkeypatch.setattr(domain.store, "execute", execute)
    if failure == "capacity":
        monkeypatch.setattr(domain.store, "record_capacity", 0)
    with pytest.raises(ReviewError):
        domain.decisions.publish(
            "project-test", TypeAdapter(DecisionRequest).validate_python(confirm()), "failure"
        )
    assert footprint(domain) == before


def test_foreign_project_and_missing_decision_are_404(memory_client):
    client, domain, _ = memory_client
    with domain.store.database.factory() as session:
        root = session.get(Project, "project-test").repository_path
        session.add(Project(id="other", name="Other", repository_path=root + "-other"))
        session.commit()
    other = domain.decisions.publish(
        "other", TypeAdapter(DecisionRequest).validate_python(confirm()), "other"
    )[1]
    before = footprint(domain)
    for identifier in (other["project_decision_id"], "missing"):
        assert (
            publish(client, remove(identifier, 0), expected=404)["error"]["code"]
            == "RESOURCE_NOT_FOUND"
        )
    assert client.get(URL.replace("project-test", "missing")).status_code == 404
    assert footprint(domain) == before


def test_pagination_freezes_version_and_rejects_cross_scope_cursor(memory_client):
    client, _, _ = memory_client
    publish(client, confirm())
    second = publish(client, confirm(1))
    first_page = client.get(URL, params={"limit": 1}).json()
    assert first_page["ruleset_version"] == 2
    publish(client, confirm(2))
    page = client.get(URL, params={"cursor": first_page["next_cursor"], "limit": 1}).json()
    assert page["ruleset_version"] == 2
    assert [x["project_decision_id"] for x in page["items"]] == [second["project_decision_id"]]
    assert page["next_cursor"] is None
    assert (
        client.get(
            URL, params={"cursor": first_page["next_cursor"], "ruleset_version": 3}
        ).status_code
        == 422
    )
    assert client.get(URL, params={"cursor": "broken"}).status_code == 422
    assert (
        client.get(URL, params={"ruleset_version": 4}).json()["error"]["code"]
        == "RULESET_VERSION_CONFLICT"
    )
    assert client.get(URL, params={"ruleset_version": 0}).json()["items"] == []


def test_same_timestamp_pagination_uses_created_at_and_id_with_frozen_view(
    memory_client, monkeypatch
):
    client, _, _ = memory_client
    identifiers = iter(("pd_z", "pd_a", "pd_0"))
    monkeypatch.setattr(decisions_module, "identity", lambda prefix: next(identifiers))
    monkeypatch.setattr(decisions_module, "now", lambda: "2026-11-01T00:00:00Z")
    publish(client, confirm())
    publish(client, confirm(1))
    first = client.get(URL, params={"limit": 1}).json()
    assert [item["project_decision_id"] for item in first["items"]] == ["pd_a"]
    publish(client, confirm(2))
    second = client.get(URL, params={"limit": 1, "cursor": first["next_cursor"]}).json()
    assert second["ruleset_version"] == first["ruleset_version"] == 2
    assert [item["project_decision_id"] for item in second["items"]] == ["pd_z"]
    assert second["next_cursor"] is None
    whole = client.get(URL, params={"ruleset_version": 2}).json()
    assert [item["project_decision_id"] for item in whole["items"]] == ["pd_a", "pd_z"]


def test_authentication_query_key_and_body_limit(memory_client):
    client, _, _ = memory_client
    key = client.headers.pop("X-API-Key")
    try:
        assert client.get(URL).status_code == 401
        assert client.post(URL, json=confirm()).status_code == 401
    finally:
        client.headers["X-API-Key"] = key
    assert client.post(URL, json=confirm()).status_code == 422
    assert publish(client, confirm(), "bad key", 422)["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"
    assert client.get(URL + "?limit=1&limit=2").status_code == 422
    assert client.get(URL + "?unknown=x").status_code == 422
    assert (
        client.post(
            URL + "?unknown=x", json=confirm(), headers={"Idempotency-Key": "q"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            URL,
            content=b"x" * (1024**2 + 1),
            headers={"Content-Type": "application/json", "Idempotency-Key": "large"},
        ).status_code
        == 413
    )


def test_selector_subset_is_exact_and_intersection_treats_omitted_as_unrestricted():
    whole = scope([CREATE], paths=["docs/api.md"])
    assert scope_subset(whole, whole)
    assert not scope_subset(scope([CREATE]), whole)
    assert not scope_subset(
        scope([{"method": "POST", "path": "/exports/"}], paths=["docs/api.md"]), whole
    )
    assert scopes_intersect(scope([CREATE]), scope(paths=["docs/api.md"]))
    assert not scopes_intersect(scope([CREATE]), scope([CANCEL]))


def test_normalized_scope_preserves_original_submission(memory_client):
    client, _, _ = memory_client
    raw = confirm(
        selected_scope=scope(
            [{"method": "post", "path": "/exports"}, CREATE], versions=["v2", "v2"]
        )
    )
    result = publish(client, raw)
    assert result["scope"] == scope([CREATE])
    assert result["original_request"] == raw


@pytest.mark.parametrize(
    "path,expected",
    [
        (None, "SCOPE_UNRESOLVED"),
        ("docs/api.md", "SUPERSEDED_SLICE"),
        ("examples/client.py", "EXACT_SCOPE_MATCH"),
    ],
)
def test_removal_unknown_propagates_and_path_completion_resolves(memory_client, path, expected):
    client, domain, body = memory_client
    old = publish(client, confirm(selected_scope=scope([CREATE])))["project_decision_id"]
    publish(client, remove(old, selected_scope=scope([CREATE], paths=["docs/api.md"])))
    target = {
        "api_version": "v2",
        "endpoint": CREATE,
        "checks": [{"key": "rule", "behavior": "核对规则"}],
    }
    if path:
        target["source_path"] = path
    body["targets"] = [target]
    accepted = create(client, body, 2)
    frozen = snapshot_input(domain, accepted["input_revision_id"])
    old_row = next(
        r for r in project_adoptions(frozen) if r["origin"]["project_decision_id"] == old
    )
    assert old_row["reason_code"] == expected
    assert (old_row["disposition"] == "adopted") is (expected == "EXACT_SCOPE_MATCH")


def test_wrong_version_is_historical_and_none_never_adopts(memory_client):
    client, domain, body = memory_client
    publish(client, confirm(selected_scope=scope([CREATE], versions=["v1"])))
    accepted = create(client, body)
    rules = project_adoptions(snapshot_input(domain, accepted["input_revision_id"]))
    assert {r["disposition"] for r in rules} == {"historical_only"}
    assert {r["reason_code"] for r in rules} == {"VERSION_OUT_OF_SCOPE"}
    accepted = client.post(REVIEWS, json=body, headers={"Idempotency-Key": "none"}).json()
    assert project_adoptions(snapshot_input(domain, accepted["input_revision_id"])) == []


def test_create_ruleset_version_rechecked_after_snapshot_preparation(memory_client, monkeypatch):
    client, domain, body = memory_client
    publish(client, confirm())
    original = domain.snapshot_reader.prepare

    def prepare(*args):
        snapshot = original(*args)
        domain.decisions.publish(
            "project-test", TypeAdapter(DecisionRequest).validate_python(confirm(1)), "raced"
        )
        return snapshot

    monkeypatch.setattr(domain.snapshot_reader, "prepare", prepare)
    body["ruleset_usage"] = {"mode": "applicable_confirmed", "expected_ruleset_version": 1}
    with pytest.raises(ReviewError, match="规则集"):
        domain.create(CreateReview.model_validate(body), "race")
    with domain.store.read() as conn:
        for table in (
            "contract_reviews",
            "contract_review_inputs",
            "contract_review_snapshots",
            "contract_review_jobs",
        ):
            assert conn.exec_driver_sql("SELECT count(*) FROM " + table).scalar_one() == 0
