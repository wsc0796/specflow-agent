"""Faulted checkpoints cloned into comparable fresh/reuse attempts, with mocked wire I/O."""

import copy
import json
import sqlite3
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from test_dynamic_workflow import ScriptedAdapter, read_action, reason, submit, terminal

from specflow.api_security import ApiSecurity
from specflow.contract_review.common import ReviewError, canonical, digest
from specflow.contract_review.profiles import dynamic_profile
from specflow.contract_review.provider import OpenAIReviewAdapter
from specflow.contract_review.replay import before_terminal, fingerprint
from specflow.contract_review.snapshot_tools import SnapshotTools
from specflow.db import Project
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.main import create_app

URL = "/api/v1/contract-reviews"


@pytest.fixture(autouse=True)
def forbid_real_http(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Replay tests forbid real HTTP")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture
def replay_app(tmp_path, git_repo, controlled_adapter):
    root, _, request = git_repo

    @contextmanager
    def start(name, *, actor_mode="direct", fault=None, disposition="adopted"):
        material_mode = actor_mode in ("rule_only", "observation_only")
        actor = ScriptedAdapter(
            controlled_adapter(),
            "delegate" if material_mode else actor_mode,
            disposition=disposition,
        )
        wire, failed = [], False

        def transport(http_request):
            nonlocal failed
            payload = json.loads(http_request.content)
            wire.append(copy.deepcopy(payload))
            data = json.loads(payload["messages"][1]["content"])
            if fault == "rate_limit":
                return httpx.Response(429, json={"error": "controlled per-step retries"})
            if (
                fault == "after_tool"
                and not failed
                and data.get("observations")
                and "candidate_report" not in data
                and "capability_id" not in data
            ):
                failed = True
                return httpx.Response(400, json={"error": "controlled suffix failure"})
            if (
                fault == "before_parent_acceptance"
                and not failed
                and data.get("child_results")
                and "candidate_report" not in data
            ):
                failed = True
                return httpx.Response(400, json={"error": "parent acceptance missing"})
            if material_mode and "capability_id" in data:
                reference = (
                    {"kind": "source", "source_ref": data["rule_materials"][0]["source_ref"]}
                    if actor_mode == "rule_only"
                    else {
                        "kind": "observation",
                        "observation_id": data["observations"][0]["observation_id"],
                    }
                )
                action = {
                    "schema_version": "contract-review-child-action.v1",
                    "action": "submit_report",
                    "reason": reason("只引用已授予且已投影材料，不新增读取。"),
                    "report": {
                        "schema_version": "contract-review-child-result.v1",
                        "status": "insufficient",
                        "findings": [],
                        "evidence_refs": [reference],
                        "limitations": ["只验证已授予材料消费，不判业务语义。"],
                        "unresolved_gaps": ["交父方形成报告。"],
                    },
                }
                result = {
                    "content": json.dumps(action, ensure_ascii=False),
                    "usage": {"input_tokens": 3, "output_tokens": 4},
                }
            elif (
                actor_mode == "observation_only"
                and not data.get("child_results")
                and not data.get("observations")
                and "candidate_report" not in data
            ):
                result = {
                    "content": json.dumps(read_action(data, "docs/api.md")),
                    "usage": {"input_tokens": 3, "output_tokens": 4},
                }
            else:
                result = actor.complete(payload)
                if material_mode and "candidate_report" not in data:
                    action = json.loads(result["content"])
                    if action["action"] == "delegate_task":
                        action["allowed_material_refs"] = (
                            [
                                ref
                                for ref in action["allowed_material_refs"]
                                if ref["kind"] == "rule"
                            ]
                            if actor_mode == "rule_only"
                            else [
                                {
                                    "kind": "observation",
                                    "observation_id": data["observations"][0]["observation_id"],
                                }
                            ]
                        )
                        result["content"] = json.dumps(action, ensure_ascii=False)
            return httpx.Response(
                200,
                json={
                    "model": payload["model"],
                    "choices": [{"message": {"content": result["content"]}}],
                    "usage": result["usage"],
                },
            )

        config = OpenAICompatibleConfig(
            api_key="synthetic-replay-test-only",
            base_url="https://provider.invalid/v1",
            model="controlled-test",
            timeout_seconds=45,
        )
        adapter = OpenAIReviewAdapter(
            config, transport=httpx.MockTransport(transport), execution_mode="test"
        )
        profile = dynamic_profile(
            "replay-test", "controlled-test", replay=True, provider_binding=adapter.binding
        )
        database = tmp_path / (name + ".sqlite")
        app = create_app(
            f"sqlite:///{database.as_posix()}",
            tmp_path / (name + "-artifacts"),
            ApiSecurity(api_key="test-key", allowed_repository_roots=(str(tmp_path),)),
            contract_review_profiles={"replay-test": profile},
            contract_review_adapter=adapter,
        )
        with TestClient(app) as client:
            with app.state.database.factory() as session:
                if session.get(Project, "project-test") is None:
                    session.add(
                        Project(id="project-test", name="Fixture", repository_path=str(root))
                    )
                    session.commit()
            client.headers["X-API-Key"] = "test-key"
            domain = app.state.contract_reviews
            if fault == "after_review":
                original = domain.worker.ledger.commit_report

                def interrupted(*args, **kwargs):
                    nonlocal failed
                    if not failed:
                        failed = True
                        raise ReviewError("INJECTED_FAILURE", "固定复核已接受，报告提交前故障。")
                    return original(*args, **kwargs)

                domain.worker.ledger.commit_report = interrupted
            body = {**copy.deepcopy(request), "execution_profile_id": "replay-test"}
            yield client, domain, body, wire, database

    return start


def clone_database(source, target):
    origin, destination = sqlite3.connect(source), sqlite3.connect(target)
    try:
        origin.backup(destination)
    finally:
        destination.close()
        origin.close()


def retry(client, accepted, state, mode, fallback="stop", key="retry"):
    request = {
        "expected_version": state["version"],
        "failed_job_id": state["job_id"],
        "input_revision_id": state["current_input_revision_id"],
        "reason": "从同一故障检查点显式重试。",
        "mode": mode,
    }
    if mode == "reuse_completed":
        request["recovery_fallback"] = fallback
    response = client.post(
        URL + "/" + accepted["review_id"] + "/retries",
        json=request,
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    return response.json()


def old_costs(domain, job_id):
    with domain.store.read() as conn:
        calls = {
            row["id"]: json.loads(row["body"])["usage"]
            for row in conn.exec_driver_sql(
                "SELECT id,body FROM contract_review_calls WHERE job_id=?", (job_id,)
            ).mappings()
        }
        entries = [
            tuple(row)
            for row in conn.exec_driver_sql(
                "SELECT id,call_id,body FROM contract_review_budget_entries "
                "WHERE job_id=? ORDER BY id",
                (job_id,),
            )
        ]
    return calls, entries


@pytest.mark.parametrize(
    ("fault", "actor_mode", "disposition"),
    [
        ("after_tool", "direct", "adopted"),
        ("after_review", "direct", "adopted"),
        ("after_review", "delegate", "adopted"),
        ("after_review", "delegate", "partial"),
        ("after_review", "delegate", "rejected"),
        ("before_parent_acceptance", "delegate", "adopted"),
    ],
)
def test_fresh_and_reuse_are_compared_from_the_same_frozen_checkpoint(
    replay_app, tmp_path, monkeypatch, fault, actor_mode, disposition
):
    counters = {"seed": 0, "fresh": 0, "reuse_completed": 0}
    phase = "seed"
    original_tool = SnapshotTools.execute

    def counted(tools, *args, **kwargs):
        counters[phase] += 1
        return original_tool(tools, *args, **kwargs)

    monkeypatch.setattr(SnapshotTools, "execute", counted)
    with replay_app("seed", fault=fault, actor_mode=actor_mode, disposition=disposition) as (
        client,
        domain,
        body,
        _,
        source_db,
    ):
        accepted = submit(client, body)
        source_state = terminal(client, accepted["review_id"])
        assert source_state["status"] == "failed", source_state
        original_costs = old_costs(domain, source_state["job_id"])
    result = {
        "fault": fault,
        "actor_mode": actor_mode,
        "disposition": disposition,
        "frozen_input_hash": source_state["input_hash"],
        "source_job_id": source_state["job_id"],
        "arms": {},
        "semantic_status": "NOT_RUN",
    }
    reports = []
    for mode in ("fresh", "reuse_completed"):
        phase = mode
        clone_database(source_db, tmp_path / (mode + ".sqlite"))
        with replay_app(mode, actor_mode=actor_mode, disposition=disposition) as (
            client,
            domain,
            _,
            wire,
            _,
        ):
            state = client.get(URL + "/" + accepted["review_id"]).json()
            assert state["input_hash"] == source_state["input_hash"]
            retried = retry(client, accepted, state, mode)
            finished = terminal(client, accepted["review_id"])
            assert finished["status"] == "completed_degraded", finished
            report = client.get(URL + "/" + accepted["review_id"] + "/report").json()
            normalized = copy.deepcopy(report["payload"])
            normalized["adopted_child_result_refs"] = [
                {k: v for k, v in review.items() if k != "child_result_ref"}
                for review in normalized["adopted_child_result_refs"]
            ]
            reports.append(normalized)
            with domain.store.read() as conn:
                receipts = [
                    dict(row)
                    for row in conn.exec_driver_sql(
                        "SELECT step_id,source_job_id,source_step_id,kind,status,body "
                        "FROM contract_review_replay_bindings WHERE job_id=? ORDER BY rowid",
                        (retried["job_id"],),
                    ).mappings()
                ]
                physical = [
                    json.loads(row["body"])
                    for row in conn.exec_driver_sql(
                        "SELECT body FROM contract_review_calls WHERE job_id=?",
                        (retried["job_id"],),
                    ).mappings()
                ]
            assert old_costs(domain, source_state["job_id"]) == original_costs
            assert finished["budget"]["model_calls"] == source_state["budget"]["model_calls"] + len(
                wire
            )
            assert sum(call["kind"] == "model" for call in physical) == len(wire)
            result["arms"][mode] = {
                "new_provider_requests": len(wire),
                "new_tool_executions": counters[mode],
                "new_physical_calls": len(physical),
                "reused_steps": [
                    {k: v for k, v in row.items() if k != "body"}
                    | {"source_call_id": json.loads(row["body"])["source_call_id"]}
                    for row in receipts
                ],
                "final_status": finished["status"],
                "report_revision_id": report["report_revision_id"],
                "final_report_payload": report["payload"],
                "cumulative_budget": finished["budget"],
                "old_call_usage_and_budget_entries_unchanged": True,
            }
    assert reports[0] == reports[1]
    expected_fresh = 3 if actor_mode == "direct" else 5
    assert result["arms"]["fresh"]["new_provider_requests"] == expected_fresh
    assert result["arms"]["fresh"]["new_tool_executions"] == 1
    assert result["arms"]["fresh"]["reused_steps"] == []
    expected_new = 2 if fault == "after_tool" else 5 if fault == "before_parent_acceptance" else 0
    assert result["arms"]["reuse_completed"]["new_provider_requests"] == expected_new
    assert result["arms"]["reuse_completed"]["new_tool_executions"] == (
        1 if fault == "before_parent_acceptance" else 0
    )
    assert all(
        row["status"] == "accepted" for row in result["arms"]["reuse_completed"]["reused_steps"]
    )
    artifact = tmp_path / ("comparison-" + fault + ".json")
    artifact.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("T08_COMPARISON_JSON=" + str(artifact))


def corrupt(database, kind):
    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        step = dict(
            conn.execute("SELECT * FROM contract_review_steps ORDER BY step_seq LIMIT 1").fetchone()
        )
        if kind == "middle_result":
            step = dict(
                conn.execute(
                    "SELECT * FROM contract_review_steps "
                    "WHERE role='tool' ORDER BY step_seq LIMIT 1"
                ).fetchone()
            )
        if kind == "missing_accepted_tail_step":
            step = dict(
                conn.execute(
                    "SELECT * FROM contract_review_steps ORDER BY step_seq DESC LIMIT 1"
                ).fetchone()
            )
        call = dict(
            conn.execute(
                "SELECT * FROM contract_review_calls WHERE step_id=?", (step["id"],)
            ).fetchone()
        )
        body, details = json.loads(step["body"]), json.loads(call["body"])
        if kind in ("result", "middle_result"):
            details["result"]["content"] = "damaged"
        elif kind == "projection":
            details["projection"]["payload"]["messages"][1]["content"] = "damaged"
        elif kind == "compatibility":
            body["compatibility"]["build"] = "unproven-upgrade"
        elif kind == "predecessor":
            body["predecessor"] = "different-observation-chain"
        elif kind == "action":
            body["action"]["tool"] = "list_sources"
        elif kind == "parent_response":
            body["parent_response"]["content"] = "different accepted response"
        elif kind == "parent_review":
            body["child_result_reviews"] = [{"child_result_ref": "foreign-child"}]
        elif kind == "missing_result":
            conn.execute("DELETE FROM contract_review_calls WHERE id=?", (call["id"],))
        elif kind == "missing_accepted_tail_step":
            conn.execute("DELETE FROM contract_review_calls WHERE step_id=?", (step["id"],))
            conn.execute("DELETE FROM contract_review_steps WHERE id=?", (step["id"],))
            return
        elif kind in ("request", "foreign_input"):
            if kind == "request":
                data = json.loads(details["projection"]["payload"]["messages"][1]["content"])
                data["runtime_clock"] = "old-runtime-clock"
                details["projection"]["payload"]["messages"][1]["content"] = canonical(data)
                details["projection"]["projection_hash"] = digest(details["projection"]["payload"])
                body["fingerprint"] = fingerprint(
                    details["projection"]["payload"],
                    details["result"],
                    details["kind"],
                    step["role"],
                )
            else:
                details["projection"]["input_hash"] = "another-input"
            body["projection_hash"] = digest(details["projection"])
        else:
            raise AssertionError(kind)
        conn.execute(
            "UPDATE contract_review_steps SET body=? WHERE id=?", (canonical(body), step["id"])
        )
        if kind != "missing_result":
            conn.execute(
                "UPDATE contract_review_calls SET body=? WHERE id=?",
                (canonical(details), call["id"]),
            )


@pytest.mark.parametrize("fallback", ["stop", "restart_fresh"])
@pytest.mark.parametrize(
    "damage",
    [
        "result",
        "projection",
        "compatibility",
        "predecessor",
        "missing_result",
        "request",
        "middle_result",
        "missing_accepted_tail_step",
        "action",
        "parent_response",
        "parent_review",
    ],
)
def test_broken_prefix_uses_only_the_explicit_fallback(replay_app, tmp_path, damage, fallback):
    with replay_app("seed", fault="after_review") as (client, _, body, _, source_db):
        accepted = submit(client, body)
        assert terminal(client, accepted["review_id"])["status"] == "failed"
    clone_database(source_db, tmp_path / "damaged.sqlite")
    corrupt(tmp_path / "damaged.sqlite", damage)
    with replay_app("damaged") as (client, domain, _, wire, _):
        state = client.get(URL + "/" + accepted["review_id"]).json()
        before = state["budget"]["model_calls"]
        retried = retry(client, accepted, state, "reuse_completed", fallback)
        final = terminal(client, accepted["review_id"])
        if fallback == "stop":
            assert final["error_code"] == "REPLAY_PREFIX_UNAVAILABLE", final
            assert wire == [] and not final["report_available"]
        else:
            assert final["status"] == "completed_degraded", final
            assert len(wire) == 3 and final["recovery"]["effective_mode"] == "fresh"
        assert final["budget"]["model_calls"] == before + len(wire)
        assert final["job_id"] == retried["job_id"]


def test_fresh_attempt_gets_its_own_dependency_retry_domain_without_refunding_review(replay_app):
    with replay_app("limited", fault="rate_limit") as (client, domain, body, wire, _):
        accepted = submit(client, body)
        first = terminal(client, accepted["review_id"])
        assert first["error_code"] == "PROVIDER_RATE_LIMITED" and len(wire) == 2
        second = retry(client, accepted, first, "fresh")
        final = terminal(client, accepted["review_id"])
        assert final["error_code"] == "PROVIDER_RATE_LIMITED" and len(wire) == 4
        assert final["budget"]["model_calls"] == 4
        with domain.store.read() as conn:
            for job_id in (first["job_id"], second["job_id"]):
                calls = conn.exec_driver_sql(
                    "SELECT step_id,physical_retry_no FROM contract_review_calls "
                    "WHERE job_id=? ORDER BY physical_retry_no",
                    (job_id,),
                ).all()
                assert len({row.step_id for row in calls}) == 1
                assert [row.physical_retry_no for row in calls] == [0, 1]


def test_terminal_order_uses_timezone_aware_instants_not_lexical_iso_strings():
    assert before_terminal("2026-11-02T00:00:00Z", "2026-11-02T00:00:00.1Z")
    assert before_terminal("2026-11-02T08:00:00+08:00", "2026-11-02T00:00:00Z")
    assert not before_terminal("2026-11-02T00:00:01Z", "2026-11-02T00:00:00Z")
    assert not before_terminal("2026-11-02T00:00:00", "2026-11-02T00:00:00Z")
    assert not before_terminal(None, "2026-11-02T00:00:00Z")


@pytest.mark.parametrize("material_mode", ["rule_only", "observation_only"])
def test_replay_consumes_explicit_materials_without_expanding_child_tool_grants(
    replay_app, tmp_path, material_mode
):
    with replay_app("seed", fault="after_review", actor_mode=material_mode) as (
        client,
        domain,
        body,
        wire,
        source_db,
    ):
        accepted = submit(client, body)
        final = terminal(client, accepted["review_id"])
        assert final["error_code"] == "INJECTED_FAILURE", final
        child_data = [
            json.loads(p["messages"][1]["content"])
            for p in wire
            if "capability_id" in json.loads(p["messages"][1]["content"])
        ]
        assert len(child_data) == 1 and child_data[0]["source_catalog"]["items"] == []
        with domain.store.read() as conn:
            row = domain.store.row(conn, "SELECT status,body FROM contract_review_child_tasks")
            assert (
                row["status"] == "accepted"
                and json.loads(row["body"])["evidence_trace"]["published_source_refs"]
            )
    clone_database(source_db, tmp_path / "consume.sqlite")
    with replay_app("consume", actor_mode=material_mode) as (client, _, _, wire, _):
        state = client.get(URL + "/" + accepted["review_id"]).json()
        retry(client, accepted, state, "reuse_completed")
        final = terminal(client, accepted["review_id"])
        assert final["status"] == "completed_degraded", final
        assert wire == []


@pytest.mark.parametrize("damage", ["late_parent", "child_package", "child_predecessor"])
@pytest.mark.parametrize("fallback", ["stop", "restart_fresh"])
def test_delegation_requires_untampered_package_and_pre_terminal_parent_acceptance(
    replay_app, tmp_path, damage, fallback
):
    with replay_app("seed", fault="after_review", actor_mode="delegate") as (
        client,
        _,
        body,
        _,
        source_db,
    ):
        accepted = submit(client, body)
        assert terminal(client, accepted["review_id"])["status"] == "failed"
    target = tmp_path / "bad-unit.sqlite"
    clone_database(source_db, target)
    with sqlite3.connect(target) as conn:
        if damage == "late_parent":
            for identifier, encoded in conn.execute("SELECT id,body FROM contract_review_steps"):
                body = json.loads(encoded)
                if body.get("child_result_reviews"):
                    body["accepted_at"] = "2999-01-01T00:00:00Z"
                    conn.execute(
                        "UPDATE contract_review_steps SET body=? WHERE id=?",
                        (canonical(body), identifier),
                    )
        elif damage == "child_predecessor":
            identifier, encoded = conn.execute(
                "SELECT id,body FROM contract_review_steps "
                "WHERE role='child' ORDER BY step_seq LIMIT 1"
            ).fetchone()
            body = json.loads(encoded)
            body["predecessor"] = "broken-child-history"
            conn.execute(
                "UPDATE contract_review_steps SET body=? WHERE id=?", (canonical(body), identifier)
            )
        else:
            identifier, encoded = conn.execute(
                "SELECT id,body FROM contract_review_child_tasks"
            ).fetchone()
            body = json.loads(encoded)
            body["result"]["status"] = "failed"
            conn.execute(
                "UPDATE contract_review_child_tasks SET body=? WHERE id=?",
                (canonical(body), identifier),
            )
    with replay_app("bad-unit", actor_mode="delegate") as (client, domain, _, wire, _):
        state = client.get(URL + "/" + accepted["review_id"]).json()
        new = retry(client, accepted, state, "reuse_completed", fallback)
        final = terminal(client, accepted["review_id"])
        if fallback == "stop":
            assert final["error_code"] == "REPLAY_PREFIX_UNAVAILABLE", final
            assert wire == []
        else:
            assert final["status"] == "completed_degraded", final
            assert len(wire) == 5 and final["recovery"]["effective_mode"] == "fresh"
        assert final["budget"]["model_calls"] == state["budget"]["model_calls"] + len(wire)
        with domain.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_replay_bindings WHERE job_id=?",
                    (new["job_id"],),
                ).scalar_one()
                == 0
            )


def test_foreign_input_cannot_be_bypassed_by_restart_fresh(replay_app, tmp_path):
    with replay_app("seed", fault="after_review") as (client, _, body, _, source_db):
        accepted = submit(client, body)
        assert terminal(client, accepted["review_id"])["status"] == "failed"
    clone_database(source_db, tmp_path / "foreign.sqlite")
    corrupt(tmp_path / "foreign.sqlite", "foreign_input")
    with replay_app("foreign") as (client, _, _, wire, _):
        state = client.get(URL + "/" + accepted["review_id"]).json()
        retry(client, accepted, state, "reuse_completed", "restart_fresh")
        final = terminal(client, accepted["review_id"])
        assert final["error_code"] == "ACTION_PERMISSION_DENIED", final
        assert wire == []


@pytest.mark.parametrize(
    ("actor_mode", "ancestor_damage", "fallback"),
    [
        ("direct", None, "stop"),
        ("delegate", None, "stop"),
        ("direct", "root", "stop"),
        ("direct", "root", "restart_fresh"),
        ("delegate", "child", "stop"),
        ("delegate", "child", "restart_fresh"),
    ],
)
def test_retry_of_replayed_attempt_preserves_transitive_provenance(
    replay_app, tmp_path, actor_mode, ancestor_damage, fallback
):
    with replay_app("seed", fault="after_review", actor_mode=actor_mode) as (
        client,
        _,
        body,
        _,
        source_db,
    ):
        accepted = submit(client, body)
        assert terminal(client, accepted["review_id"])["status"] == "failed"
    clone_database(source_db, tmp_path / "second.sqlite")
    with replay_app("second", fault="after_review", actor_mode=actor_mode) as (
        client,
        _,
        _,
        wire,
        second_db,
    ):
        state = client.get(URL + "/" + accepted["review_id"]).json()
        second = retry(client, accepted, state, "reuse_completed")
        assert terminal(client, accepted["review_id"])["status"] == "failed"
        assert wire == []
    clone_database(second_db, tmp_path / "third.sqlite")
    if ancestor_damage:
        with sqlite3.connect(tmp_path / "third.sqlite") as conn:
            role = "child" if ancestor_damage == "child" else "analysis"
            identifier, encoded = conn.execute(
                "SELECT id,body FROM contract_review_steps WHERE job_id=? AND role=? "
                "ORDER BY step_seq LIMIT 1",
                (accepted["job_id"], role),
            ).fetchone()
            damaged = json.loads(encoded)
            damaged["predecessor"] = "broken-original-ancestor-history"
            conn.execute(
                "UPDATE contract_review_steps SET body=? WHERE id=?",
                (canonical(damaged), identifier),
            )
    with replay_app("third", actor_mode=actor_mode) as (client, domain, _, wire, _):
        state = client.get(URL + "/" + accepted["review_id"]).json()
        third = retry(client, accepted, state, "reuse_completed", fallback, key="retry-third")
        final = terminal(client, accepted["review_id"])
        if ancestor_damage:
            if fallback == "stop":
                assert final["error_code"] == "REPLAY_PREFIX_UNAVAILABLE", final
                assert wire == []
            else:
                assert final["status"] == "completed_degraded", final
                assert len(wire) == (3 if actor_mode == "direct" else 5)
                assert final["recovery"]["effective_mode"] == "fresh"
            assert final["budget"]["model_calls"] == state["budget"]["model_calls"] + len(wire)
            return
        assert final["status"] == "completed_degraded", final
        assert wire == [] and third["retry_of_job_id"] == second["job_id"]
        with domain.store.read() as conn:
            sources = (
                conn.exec_driver_sql(
                    "SELECT DISTINCT source_job_id FROM contract_review_replay_bindings "
                    "WHERE job_id=?",
                    (third["job_id"],),
                )
                .scalars()
                .all()
            )
        assert sources == [second["job_id"]]
