"""Frozen project decisions cross reviews, never silently upgrade existing inputs."""

import copy
import json
import threading

import pytest
from pydantic import TypeAdapter
from test_checkpoints import HumanAdapter, answer, batch, post, revision, terminal, waiting
from test_decision_scope import (
    CANCEL,
    CREATE,
    REVIEWS,
    URL,
    confirm,
    create,
    project_adoptions,
    publish,
    remove,
    scope,
    snapshot_input,
)
from test_decision_scope import memory_client as memory_client

from specflow.contract_review.common import ReviewError, digest
from specflow.contract_review.decisions import DecisionRequest
from specflow.contract_review.dynamic_context import RunState
from specflow.contract_review.profiles import dynamic_profile
from specflow.contract_review.report_validation import validate_report, validate_rule_body
from specflow.contract_review.schemas import CreateReview
from specflow.contract_review.snapshot_tools import SnapshotTools
from specflow.contract_review.tool_protocol import CAPABILITIES
from specflow.db import Project


def enable(test_profile, engine="v1"):
    if engine == "v2":
        value = dynamic_profile(test_profile["profile_id"], test_profile["model"])
        test_profile.clear()
        test_profile.update(value)
    test_profile["options"]["project_memory"] = True


def use(body, version):
    return {
        **body,
        "ruleset_usage": {"mode": "applicable_confirmed", "expected_ruleset_version": version},
    }


def sources_for(domain, frozen):
    with domain.store.read() as conn:
        return domain.checkpoints._snapshot(conn, frozen)["files"]


def test_two_reviews_reuse_confirmed_rule_with_exact_frozen_identity(memory_client):
    client, domain, body = memory_client
    decision = publish(client, confirm())
    first, second = create(client, body), create(client, body, key="another-review")
    for accepted in (first, second):
        frozen = snapshot_input(domain, accepted["input_revision_id"])
        assert frozen["adopted_ruleset_version"] == 1
        assert frozen["input_hash"] == digest(
            {k: v for k, v in frozen.items() if k != "input_hash"}
        )
        for record in project_adoptions(frozen):
            assert record["disposition"] == "adopted"
            assert record["origin"] == {
                "kind": "project_decision",
                "project_decision_id": decision["project_decision_id"],
                "introduced_ruleset_version": 1,
            }
            assert record["input_revision_id"] == accepted["input_revision_id"]
            assert record["snapshot_id"] == frozen["snapshot_id"]
            assert record["commit_sha"] == body["source"]["commit_sha"]
            assert record["matched_target"] in frozen["target_manifest"]
            assert record["body_hash"] == digest(decision["text"].encode())
    assert len(client.get(URL).json()["items"]) == 1


def test_scope_dimensions_never_join_across_distinct_targets(memory_client):
    client, domain, body = memory_client
    publish(client, confirm(selected_scope=scope([CREATE], paths=["docs/api.md"])))
    body["targets"] = [
        {
            "api_version": "v2",
            "endpoint": CREATE,
            "source_path": "src/api.py",
            "checks": [{"key": "a", "behavior": "核对"}],
        },
        {
            "api_version": "v2",
            "endpoint": CANCEL,
            "source_path": "docs/api.md",
            "checks": [{"key": "b", "behavior": "核对"}],
        },
    ]
    accepted = create(client, body)
    assert {
        r["reason_code"]
        for r in project_adoptions(snapshot_input(domain, accepted["input_revision_id"]))
    } == {"TARGET_OUT_OF_SCOPE"}


@pytest.mark.parametrize("engine", ["v1", "v2"])
def test_actual_parent_and_fixed_review_consume_full_project_text(
    running_app, controlled_adapter, test_profile, engine
):
    enable(test_profile, engine)

    class RuleUsingAdapter(controlled_adapter):
        def complete(self, payload):
            result = super().complete(payload)
            data = json.loads(payload["messages"][1]["content"])
            if "candidate_report" not in data:
                action = json.loads(result["content"])
                action["report"]["rule_uses"] = [
                    {
                        "adoption_id": rule["adoption_id"],
                        "usage": "support",
                        "explanation": "引用已冻结项目规则。",
                    }
                    for rule in data["adoption_records"]
                    if rule["origin"]["kind"] == "project_decision"
                    and rule["disposition"] == "adopted"
                ]
                result["content"] = json.dumps(action, ensure_ascii=False)
            return result

    adapter = RuleUsingAdapter()
    text = "明确项目规则：" + "保留原文条件。" * 65 + "尾部不可省略：仅 queued 可取消。"
    with running_app(adapter) as (client, domain, body):
        publish(client, confirm(selected_scope=scope([CREATE]), text=text))
        accepted = create(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "completed_degraded", state
        assert len(adapter.requests) == 2
        for payload in adapter.requests:
            data = json.loads(payload["messages"][1]["content"])
            rules = project_adoptions({"adoption_records": data["adoption_records"]})
            assert rules and all(r["body"] == text for r in rules)
            assert "尾部不可省略" in payload["messages"][1]["content"]
        report = client.get(REVIEWS + "/" + accepted["review_id"] + "/report").json()
        assert report["adopted_ruleset_version"] == 1
        assert all(
            r["report_usage"]["usage"] == "support"
            for r in report["rules"]
            if r["origin"]["kind"] == "project_decision"
        )
        assert {r["body"] for r in project_adoptions({"adoption_records": report["rules"]})} == {
            text
        }
        with domain.store.read() as conn:
            calls = conn.exec_driver_sql(
                "SELECT body FROM contract_review_calls ORDER BY rowid"
            ).all()
            for row in calls:
                materials = json.loads(row[0])["projection"]["material_entries"]
                assert any(m.get("body") == text and "adoption_id" in m for m in materials)


def test_publication_never_rewrites_running_queued_or_completed_inputs(
    running_app, controlled_adapter, test_profile
):
    enable(test_profile)
    pause = threading.Event()
    adapter = controlled_adapter(pauses={1: pause})
    with running_app(adapter, timeout=5.0) as (client, domain, body):
        publish(client, confirm())
        first = create(client, body)
        assert adapter.entered[1].wait(3)
        original = snapshot_input(domain, first["input_revision_id"])
        second = create(client, body, key="queued")
        queued = snapshot_input(domain, second["input_revision_id"])
        publish(client, confirm(1, text="新发布规则"))
        for accepted in (first, second):
            state = client.get(REVIEWS + "/" + accepted["review_id"]).json()
            assert state["adopted_ruleset_version"] == 1
            assert state["current_ruleset_version"] == 2
        assert snapshot_input(domain, first["input_revision_id"]) == original
        assert snapshot_input(domain, second["input_revision_id"]) == queued
        pause.set()
        for accepted in (first, second):
            state = terminal(client, accepted["review_id"])
            assert state["status"] == "completed_degraded", state
        report = client.get(REVIEWS + "/" + first["review_id"] + "/report").json()
        publish(client, confirm(2))
        assert client.get(REVIEWS + "/" + first["review_id"] + "/report").json() == report
        assert snapshot_input(domain, first["input_revision_id"]) == original


def test_explicit_revision_switches_ruleset_and_preserves_history_and_budget(
    running_app, controlled_adapter, test_profile
):
    enable(test_profile)
    with running_app(controlled_adapter()) as (client, domain, body):
        old = publish(client, confirm())["project_decision_id"]
        accepted = create(client, body)
        state = terminal(client, accepted["review_id"])
        report = client.get(REVIEWS + "/" + accepted["review_id"] + "/report").json()
        frozen = snapshot_input(domain, accepted["input_revision_id"])
        publish(client, remove(old, selected_scope=scope([CREATE]), operation="withdraw"))
        next_response = post(
            client,
            accepted["review_id"],
            revision(
                state, ruleset_usage={"mode": "applicable_confirmed", "expected_ruleset_version": 2}
            ),
            "new-rules",
            "revisions",
        )
        assert next_response.status_code == 202, next_response.text
        updated = snapshot_input(domain, next_response.json()["input_revision_id"])
        assert updated["snapshot_id"] == frozen["snapshot_id"]
        assert updated["target_manifest"] == frozen["target_manifest"]
        assert updated["check_manifest"] == frozen["check_manifest"]
        assert {r["reason_code"] for r in project_adoptions(updated)} == {"WITHDRAWN_SLICE"}
        new_state = terminal(client, accepted["review_id"])
        assert new_state["budget"]["model_calls"] > state["budget"]["model_calls"]
        assert (
            client.get(
                REVIEWS + "/" + accepted["review_id"] + "/report",
                params={"report_revision_id": report["report_revision_id"]},
            ).json()
            == report
        )


def test_answer_derived_and_unrelated_revision_keep_frozen_old_ruleset(
    running_app, controlled_adapter, test_profile
):
    enable(test_profile)
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        publish(client, confirm())
        review_id, state, report = waiting(client, use(body, 1))
        publish(client, confirm(1))
        result = post(client, review_id, batch(state, report, [answer(), answer("q_material")]))
        assert result.status_code == 202, result.text
        frozen = snapshot_input(domain, result.json()["input_revision_id"])
        assert frozen["adopted_ruleset_version"] == 1
        assert all(r["adopted_ruleset_version"] == 1 for r in project_adoptions(frozen))
        state = terminal(client, review_id)
        assert state["status"] == "completed_degraded"
        result = post(
            client,
            review_id,
            revision(state, request="仅修改本次请求，继续采用已冻结规则。"),
            "unrelated",
            "revisions",
        )
        assert result.status_code == 202, result.text
        unchanged = snapshot_input(domain, result.json()["input_revision_id"])
        assert unchanged["adopted_ruleset_version"] == 1
        assert len(project_adoptions(unchanged)) == len(project_adoptions(frozen))
        assert len(client.get(URL).json()["items"]) == 2


def test_local_answers_need_separate_publication_and_provenance_is_owned(
    running_app, controlled_adapter, test_profile
):
    enable(test_profile)
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        response = post(client, review_id, batch(state, report))
        assert response.status_code == 200, response.text
        resolution_id = response.json()["accepted_resolution_ids"][0]
        assert client.get(URL).json()["items"] == []
        old = snapshot_input(domain, state["current_input_revision_id"])
        source_id = sources_for(domain, old)[0]["source_id"]
        payload = confirm()
        payload["provenance"] = {
            "kind": "review_record",
            "review_id": review_id,
            "report_revision_id": report["report_revision_id"],
            "resolution_ids": [resolution_id],
            "source_refs": [{"source_id": source_id, "selector": {"kind": "full"}}],
            "claimed_approver": "来源自称身份",
        }
        published = publish(client, payload)
        assert published["actor_subject"] == "shared-service"
        assert published["provenance"]["claimed_approver"] == "来源自称身份"
        # A different review's otherwise valid source/report/answer cannot be spliced in.
        other = create(client, body, 1, key="second-provenance-review")
        other_state = terminal(client, other["review_id"])
        other_report = client.get(REVIEWS + "/" + other["review_id"] + "/report").json()
        other_answer = post(client, other["review_id"], batch(other_state, other_report))
        other_frozen = snapshot_input(domain, other["input_revision_id"])
        for field, value in (
            ("report_revision_id", other_report["report_revision_id"]),
            ("resolution_ids", other_answer.json()["accepted_resolution_ids"]),
            (
                "source_refs",
                [
                    {
                        "source_id": sources_for(domain, other_frozen)[0]["source_id"],
                        "selector": {"kind": "full"},
                    }
                ],
            ),
        ):
            bad = copy.deepcopy(payload)
            bad["expected_ruleset_version"] = 1
            bad["provenance"][field] = value
            publish(client, bad, "cross-" + field, 404)
        with domain.store.database.factory() as session:
            root = session.get(Project, "project-test").repository_path
            session.add(Project(id="other-project", name="Other", repository_path=root + "-other"))
            session.commit()
        response = client.post(
            URL.replace("project-test", "other-project"),
            json=payload,
            headers={"Idempotency-Key": "foreign-project"},
        )
        assert response.status_code == 404
        for field, value in (
            ("review_id", "foreign"),
            ("report_revision_id", "foreign"),
            ("resolution_ids", ["foreign"]),
            ("source_refs", [{"source_id": "foreign", "selector": {"kind": "full"}}]),
        ):
            bad = copy.deepcopy(payload)
            bad["expected_ruleset_version"] = 1
            bad["provenance"][field] = value
            assert (
                publish(client, bad, "bad-" + field, 404)["error"]["code"] == "RESOURCE_NOT_FOUND"
            )
        bad = copy.deepcopy(payload)
        bad["expected_ruleset_version"] = 1
        bad["provenance"]["source_refs"][0]["selector"] = {
            "kind": "lines",
            "start_line": 99999,
            "end_line": 99999,
        }
        assert (
            publish(client, bad, "bad-selector", 422)["error"]["code"]
            == "INVALID_AUTHORITY_BINDING"
        )


def test_excluded_project_rule_cannot_support_report_or_forge_origin(
    running_app, controlled_adapter, test_profile
):
    enable(test_profile)
    with running_app(controlled_adapter()) as (client, domain, body):
        old = publish(client, confirm())["project_decision_id"]
        publish(client, remove(old, selected_scope=scope([CREATE]), operation="withdraw"))
        accepted = create(client, body, 2)
        assert terminal(client, accepted["review_id"])["status"] == "completed_degraded"
        frozen = snapshot_input(domain, accepted["input_revision_id"])
        report = client.get(REVIEWS + "/" + accepted["review_id"] + "/report").json()["payload"]
        rule = project_adoptions(frozen)[0]
        report["rule_uses"] = [
            {
                "adoption_id": rule["adoption_id"],
                "usage": "support",
                "explanation": "错误采用已撤回旧规则",
            }
        ]
        with pytest.raises(ValueError, match="Unadopted rule"):
            validate_report(report, frozen, {}, [])
        altered = copy.deepcopy(rule)
        altered["body"] += "篡改"
        with pytest.raises(ValueError, match="damaged"):
            validate_rule_body(altered, {}, [])
        altered = copy.deepcopy(rule)
        altered["body_ref"]["project_decision_id"] = "fake"
        with pytest.raises(ValueError, match="another origin"):
            validate_rule_body(altered, {}, [])
        report["rule_uses"][0]["adoption_id"] = "invented-decision"
        with pytest.raises(ValueError, match="Unknown adoption"):
            validate_report(report, frozen, {}, [])


def test_rule_only_child_projection_has_full_body_but_no_provenance_tool_grants(memory_client):
    client, domain, body = memory_client
    publish(client, confirm())
    accepted = create(client, body)
    frozen = snapshot_input(domain, accepted["input_revision_id"])
    frozen["execution_profile"] = dynamic_profile("child-test", "controlled-test")
    rules = project_adoptions(frozen)
    sources = {item["source_id"]: item for item in sources_for(domain, frozen)}
    context = {
        "frozen": frozen,
        "sources": sources,
        "verification_evidence": [],
        "child_id": "child",
        "capability_id": next(iter(CAPABILITIES)),
        "expected_evidence": [],
    }
    tools = SnapshotTools(sources, frozen["snapshot_id"], grants={})
    state = RunState(context, tools, rule_ids={rules[0]["adoption_id"]})
    data, entries = state.build("analysis")
    assert data["rule_materials"][0]["body"] == rules[0]["body"]
    assert entries[0]["body_hash"] == rules[0]["body_hash"]
    assert tools.grants == {}
    assert data["source_catalog"]["items"] == []
    assert len(data["adoption_records"]) == 1


def test_stale_ruleset_create_is_rejected_before_snapshot_io(memory_client, monkeypatch):
    _, domain, body = memory_client
    domain.decisions.publish(
        "project-test", TypeAdapter(DecisionRequest).validate_python(confirm()), "publish"
    )

    def forbidden(*args):
        pytest.fail("Stale ruleset should reject before snapshot I/O")

    monkeypatch.setattr(domain.snapshot_reader, "prepare", forbidden)
    with pytest.raises(ReviewError) as error:
        domain.create(CreateReview.model_validate(use(body, 0)), "stale")
    assert error.value.code == "RULESET_VERSION_CONFLICT"


@pytest.mark.parametrize("engine", ["v1", "v2"])
def test_mandatory_project_body_overflow_fails_without_truncation_or_call(
    running_app, controlled_adapter, test_profile, engine
):
    enable(test_profile, engine)
    adapter = controlled_adapter()
    with running_app(adapter) as (client, _, body):
        publish(client, confirm(text="完整条件" * 3000))
        accepted = create(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "failed", state
        assert state["error_code"] == "BUDGET_EXHAUSTED"
        assert adapter.requests == []


def test_disabled_selected_profile_requires_explicit_none(memory_client):
    client, domain, body = memory_client
    profile = copy.deepcopy(next(iter(domain.profiles.values())))
    profile["profile_id"] = "no-memory"
    profile["options"]["project_memory"] = False
    domain.profiles["no-memory"] = profile
    body["execution_profile_id"] = "no-memory"
    response = client.post(
        REVIEWS, json=use(body, 0), headers={"Idempotency-Key": "disabled-profile"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OPTION_NOT_ENABLED"
    response = client.post(REVIEWS, json=body, headers={"Idempotency-Key": "explicit-none"})
    assert response.status_code == 202


def test_ruleset_change_excludes_local_answers_and_stale_revision_is_atomic(
    running_app, controlled_adapter, test_profile
):
    enable(test_profile)
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        publish(client, confirm())
        review_id, state, report = waiting(client, use(body, 1))
        partial = post(client, review_id, batch(state, report))
        resolution = partial.json()["accepted_resolution_ids"][0]
        state = client.get(REVIEWS + "/" + review_id).json()
        publish(client, confirm(1))
        old = snapshot_input(domain, state["current_input_revision_id"])
        stale = post(
            client,
            review_id,
            revision(
                state, ruleset_usage={"mode": "applicable_confirmed", "expected_ruleset_version": 1}
            ),
            "stale-rules",
            "revisions",
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "RULESET_VERSION_CONFLICT"
        assert snapshot_input(domain, state["current_input_revision_id"]) == old
        result = post(
            client,
            review_id,
            revision(
                state, ruleset_usage={"mode": "applicable_confirmed", "expected_ruleset_version": 2}
            ),
            "switch-rules",
            "revisions",
        )
        assert result.status_code == 202, result.text
        updated = snapshot_input(domain, result.json()["input_revision_id"])
        assert updated["resolutions"] == []
        assert updated["resolution_adoptions"][0]["resolution_id"] == resolution
        assert updated["resolution_adoptions"][0]["status"] == "excluded"


def test_revision_rechecks_selected_version_after_snapshot_preparation(memory_client, monkeypatch):
    client, domain, body = memory_client
    publish(client, confirm())
    accepted = create(client, body)
    with domain.store.transaction() as conn:
        domain.store.execute(
            conn,
            "UPDATE contract_review_jobs SET status='completed' WHERE id=:id",
            id=accepted["job_id"],
        )
        domain.store.execute(
            conn,
            "UPDATE contract_reviews SET status='completed_degraded' WHERE id=:id",
            id=accepted["review_id"],
        )
    state = client.get(REVIEWS + "/" + accepted["review_id"]).json()
    original_input = snapshot_input(domain, accepted["input_revision_id"])
    publish(client, confirm(1))
    original = domain.snapshot_reader.prepare

    def prepare(*args):
        snapshot = original(*args)
        domain.decisions.publish(
            "project-test",
            TypeAdapter(DecisionRequest).validate_python(confirm(2)),
            "raced-revision",
        )
        return snapshot

    monkeypatch.setattr(domain.snapshot_reader, "prepare", prepare)
    source = copy.deepcopy(body["source"])
    source["groups"].append({"role": "decision_reference", "paths": ["src/api.py"]})
    result = post(
        client,
        accepted["review_id"],
        revision(
            state,
            source=source,
            ruleset_usage={"mode": "applicable_confirmed", "expected_ruleset_version": 2},
        ),
        "raced",
        "revisions",
    )
    assert result.status_code == 409, result.text
    assert result.json()["error"]["code"] == "RULESET_VERSION_CONFLICT"
    assert snapshot_input(domain, accepted["input_revision_id"]) == original_input
    assert (
        client.get(REVIEWS + "/" + accepted["review_id"]).json()["current_input_revision_id"]
        == accepted["input_revision_id"]
    )
    with domain.store.read() as conn:
        for table in (
            "contract_review_inputs",
            "contract_review_jobs",
            "contract_review_snapshots",
        ):
            assert conn.exec_driver_sql("SELECT count(*) FROM " + table).scalar_one() == 1
