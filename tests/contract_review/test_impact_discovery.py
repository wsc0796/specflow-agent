"""Offline impact discovery, real SQLite adoption and shared physical-I/O contracts."""

import copy
import json
import shutil
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from specflow.api_security import ApiSecurity
from specflow.contract_review.common import ReviewError, digest
from specflow.contract_review.impact_schemas import discovery_profile
from specflow.contract_review.shared_ledger import SharedLedger
from specflow.db import Project
from specflow.main import create_app

URL = "/api/v1/contract-impact-discoveries"
REVIEW = "/api/v1/contract-reviews"


class ImpactAdapter:
    execution_mode = "test"

    def __init__(self, fallback, *, transform=None, pause=None, pause_kind="impact", usage=True):
        self.fallback, self.transform = fallback, transform
        self.requests = []
        self.pause, self.pause_kind = pause, pause_kind
        self.entered = threading.Event()
        self.usage = usage

    def complete(self, payload):
        self.requests.append(copy.deepcopy(payload))
        data = json.loads(payload["messages"][1]["content"])
        impact = "change_request" in data
        if self.pause is not None and ((self.pause_kind == "impact") == impact):
            pause, self.pause = self.pause, None
            self.entered.set()
            assert pause.wait(8), "Test did not release paused adapter"
        if not impact:
            return self.fallback.complete(payload)
        refs = {
            material["source_ref"]["source_id"]: material["source_ref"]
            for material in [*data["authority_materials"], *data["cited_materials"]]
        }
        catalog = data["source_catalog"]["items"]
        unread = next((source for source in catalog if source["source_id"] not in refs), None)
        reason = dict(
            gap="受控工具/协议检查", evidence_refs=[], expected_information="只验证程序合同"
        )
        if unread:
            action = dict(
                schema_version="contract-impact-action.v1",
                action="tool_call",
                reason=reason,
                tool="read_source",
                arguments=dict(
                    source_id=unread["source_id"], start_line=1, end_line=unread["line_count"]
                ),
            )
        else:
            candidates = []
            for source in catalog:
                if source["path"] == "src/metrics.py":
                    continue
                candidates.append(
                    dict(
                        local_key="c" + str(len(candidates)),
                        source_path=source["path"],
                        artifact_role=source["roles"][0],
                        api_version="v2",
                        endpoint=dict(method="POST", path="/exports"),
                        relation="observed",
                        rationale="受控输出仅证明工程契约，不证明语义召回",
                        suggested_checks=[
                            dict(key="response_field", behavior="核对创建响应字段与采用契约")
                        ],
                        source_refs=[refs[source["source_id"]]],
                        observation_refs=[],
                        unknowns=[],
                    )
                )
            action = dict(
                schema_version="contract-impact-action.v1",
                action="submit_candidates",
                reason=reason,
                candidates=candidates,
                unresolved=[],
            )
        if self.transform:
            action = self.transform(action, data)
        return dict(
            content=json.dumps(action, ensure_ascii=False),
            model=payload["model"],
            usage=dict(input_tokens=3, output_tokens=4) if self.usage else {},
        )


@pytest.fixture
def impact_app(tmp_path, git_repo, test_profile, controlled_adapter):
    root, git, original = git_repo
    (root / "tests").mkdir()
    (root / "tests/test_create_export.py").write_text(
        'def test_create_export(client):\n    response = client.post("/exports")\n'
        '    assert response.status_code == 201\n    assert set(response.json()) == {"id"}\n',
        encoding="utf-8",
    )
    (root / "src/metrics.py").write_text(
        'def record_metric(job_id):\n    return {"metric_label": job_id}\n', encoding="utf-8"
    )
    git("add", ".")
    git("commit", "-qm", "Local impact-only static controls")
    original["source"]["commit_sha"] = git("rev-parse", "HEAD")
    original["source"]["groups"].extend(
        [
            dict(role="test", paths=["tests/test_create_export.py"]),
            dict(role="implementation", paths=["src/metrics.py"]),
        ]
    )

    @contextmanager
    def start(
        *,
        transform=None,
        pause=None,
        pause_kind="impact",
        usage=True,
        impact_settings=None,
        review_settings=None,
        worker=True,
        adapter_override=None,
    ):
        profile = discovery_profile("impact-test", "controlled-test")
        profile.update(impact_settings or {})
        formal = {**test_profile, **(review_settings or {})}
        adapter = ImpactAdapter(
            controlled_adapter(),
            transform=transform,
            pause=pause,
            pause_kind=pause_kind,
            usage=usage,
        )
        adapter = adapter_override or adapter
        app = create_app(
            f"sqlite:///{(tmp_path / 'impact.sqlite').as_posix()}",
            tmp_path / "artifacts",
            ApiSecurity(api_key="test-impact-key", allowed_repository_roots=(str(tmp_path),)),
            contract_review_profiles={formal["profile_id"]: formal},
            contract_review_adapter=adapter if worker else None,
            contract_impact_profiles={profile["profile_id"]: profile},
        )
        with TestClient(app) as client:
            with app.state.database.factory() as session:
                if session.get(Project, "project-test") is None:
                    session.add(
                        Project(id="project-test", name="Impact", repository_path=str(root))
                    )
                    session.commit()
            client.headers["X-API-Key"] = "test-impact-key"
            body = dict(
                project_id="project-test",
                change_request="核对 v2 创建响应 job_id 规则的影响",
                source=copy.deepcopy(original["source"]),
                authority_bindings=copy.deepcopy(original["authority_bindings"]),
                ruleset_usage=dict(mode="none"),
                execution_profile_id=profile["profile_id"],
            )
            try:
                yield client, app.state.contract_reviews, body, adapter, copy.deepcopy(original)
            finally:
                if pause:
                    pause.set()

    return start


def post(client, path, body, key="impact-command"):
    return client.post(path, json=body, headers={"Idempotency-Key": key})


def terminal(client, path):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] not in ("queued", "running"):
            return result
        time.sleep(0.01)
    raise AssertionError("Offline task did not reach a terminal state")


def discover(client, body, key="discover"):
    response = post(client, URL, body, key)
    assert response.status_code == 202, response.text
    discovery_id = response.json()["discovery_id"]
    state = terminal(client, URL + "/" + discovery_id)
    assert state["status"] == "completed", state
    return discovery_id, state


def adoption(state, original):
    formal = copy.deepcopy(original)
    formal["execution_profile_id"] = "controlled-test-v1"
    formal["targets"], dispositions = [], []
    for candidate in state["catalog"]["candidates"]:
        if candidate["artifact_role"] in ("documentation", "example"):
            index = len(formal["targets"])
            formal["targets"].append(
                {key: candidate[key] for key in ("api_version", "endpoint", "source_path")}
            )
            formal["targets"][-1]["checks"] = candidate["suggested_checks"]
            dispositions.append(
                dict(candidate_id=candidate["candidate_id"], disposition="take", target_index=index)
            )
        else:
            dispositions.append(
                dict(
                    candidate_id=candidate["candidate_id"],
                    disposition="exclude",
                    reason="本次只采用文档和示例；保留其他候选及理由",
                )
            )
    return dict(
        catalog_hash=state["catalog"]["catalog_hash"],
        dispositions=dispositions,
        destination=dict(kind="create", request=formal),
    )


def counts(service):
    with service.store.read() as conn:
        return tuple(
            conn.exec_driver_sql("SELECT count(*) FROM " + table).scalar_one()
            for table in (
                "contract_reviews",
                "contract_review_inputs",
                "contract_review_jobs",
                "contract_impact_adoptions",
            )
        )


def test_discovery_actual_projection_and_atomic_create_adoption(impact_app):
    with impact_app() as (client, service, body, adapter, original):
        discovery_id, state = discover(client, body)
        assert {c["artifact_role"] for c in state["catalog"]["candidates"]} == {
            "contract",
            "implementation",
            "documentation",
            "example",
            "test",
        }
        assert all(c["source_path"] != "src/metrics.py" for c in state["catalog"]["candidates"])
        assert counts(service) == (0, 0, 0, 0)
        with service.store.read() as conn:
            calls = [
                json.loads(row[0])
                for row in conn.execute(
                    text("SELECT body FROM contract_impact_calls WHERE discovery_id=:id"),
                    dict(id=discovery_id),
                )
            ]
        projected = [call["projection"]["payload"] for call in calls if call["kind"] == "model"]
        assert {digest(wire) for wire in projected} == {digest(wire) for wire in adapter.requests}
        assert all(call["local_io_state"] == "quiesced" for call in calls)
        command = adoption(state, original)
        response = post(client, URL + "/" + discovery_id + "/adoptions", command, "adopt")
        assert response.status_code == 202, response.text
        accepted = response.json()
        final = terminal(client, REVIEW + "/" + accepted["review_id"])
        assert final["report_available"]
        with service.store.read() as conn:
            frozen = service.verifications.input(
                conn, accepted["review_id"], accepted["input_revision_id"]
            )
        assert {t["source_path"] for t in frozen["target_manifest"]} == {
            "docs/api.md",
            "examples/client.py",
        }
        assert frozen["impact_origin"]["adoption_id"] == accepted["adoption_id"]
        assert len(frozen["impact_origin"]["candidate_mapping"]) == 2
        assert counts(service) == (1, 1, 1, 1)
        assert (
            post(client, URL + "/" + discovery_id + "/adoptions", command, "adopt").json()
            == accepted
        )
        changed = copy.deepcopy(command)
        next(c for c in changed["dispositions"] if c["disposition"] == "exclude")["reason"] = (
            "另一处置"
        )
        assert (
            post(client, URL + "/" + discovery_id + "/adoptions", changed, "adopt").status_code
            == 409
        )
        assert counts(service) == (1, 1, 1, 1)


def test_adoption_revision_preserves_existing_identity_and_history(impact_app):
    with impact_app() as (client, service, body, _, original):
        discovery_id, state = discover(client, body)
        command = adoption(state, original)
        initial = copy.deepcopy(command["destination"]["request"])
        initial["targets"] = initial["targets"][:1]
        created = post(client, REVIEW, initial, "initial-review").json()
        old_status = terminal(client, REVIEW + "/" + created["review_id"])
        old_report = client.get(REVIEW + "/" + created["review_id"] + "/report").json()
        with service.store.read() as conn:
            old = service.verifications.input(
                conn, created["review_id"], created["input_revision_id"]
            )
        command["destination"] = dict(
            kind="revise",
            review_id=created["review_id"],
            request=dict(
                expected_version=old_status["version"],
                base_input_revision_id=created["input_revision_id"],
                change_reason="明确采用示例目标，保留原文档目标",
                targets=command["destination"]["request"]["targets"],
            ),
        )
        response = post(client, URL + "/" + discovery_id + "/adoptions", command)
        assert response.status_code == 202, response.text
        accepted = response.json()
        terminal(client, REVIEW + "/" + created["review_id"])
        with service.store.read() as conn:
            revised = service.verifications.input(
                conn, created["review_id"], accepted["input_revision_id"]
            )
        assert revised["target_manifest"][0] == old["target_manifest"][0]
        assert revised["check_manifest"][0] == old["check_manifest"][0]
        assert len(revised["target_manifest"]) == len(revised["check_manifest"]) == 2
        historical = client.get(
            REVIEW + "/" + created["review_id"] + "/report",
            params=dict(report_revision_id=old_report["report_revision_id"]),
        )
        assert historical.json() == old_report
        assert counts(service) == (1, 2, 2, 1)


def test_adoption_fault_rolls_back_formal_input_job_snapshot_and_record(impact_app, monkeypatch):
    with impact_app() as (client, service, body, _, original):
        discovery_id, state = discover(client, body)
        command = adoption(state, original)
        original_event = service.impacts.event
        with service.store.read() as conn:
            before = conn.exec_driver_sql(
                "SELECT count(*) FROM contract_review_snapshots"
            ).scalar_one()

        def fault(conn, owner, kind, payload):
            if kind == "adoption_recorded":
                raise ReviewError("EVIDENCE_PERSISTENCE_FAILED", "受控事务故障", 503)
            return original_event(conn, owner, kind, payload)

        monkeypatch.setattr(service.impacts, "event", fault)
        assert post(client, URL + "/" + discovery_id + "/adoptions", command).status_code == 503
        assert counts(service) == (0, 0, 0, 0)
        with service.store.read() as conn:
            assert (
                conn.exec_driver_sql("SELECT count(*) FROM contract_review_snapshots").scalar_one()
                == before
            )
        monkeypatch.setattr(service.impacts, "event", original_event)
        assert post(client, URL + "/" + discovery_id + "/adoptions", command).status_code == 202


def test_all_exclusions_are_auditable_and_do_not_create_review(impact_app):
    with impact_app() as (client, service, body, _, _):
        discovery_id, state = discover(client, body)
        command = dict(
            catalog_hash=state["catalog"]["catalog_hash"],
            dispositions=[
                dict(candidate_id=c["candidate_id"], disposition="exclude", reason="本次不采用")
                for c in state["catalog"]["candidates"]
            ],
        )
        response = post(client, URL + "/" + discovery_id + "/adoptions", command)
        assert response.status_code == 201, response.text
        assert counts(service) == (0, 0, 0, 1)
        events, cursor = [], None
        while True:
            page = client.get(
                URL + "/" + discovery_id + "/events",
                params={"limit": 3, **({"cursor": cursor} if cursor else {})},
            ).json()
            events.extend(page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len({event["event_id"] for event in events}) == len(events)
        adopted = next(event for event in events if event["event_type"] == "adoption_recorded")
        detail = client.get(URL + "/" + discovery_id + "/events/" + adopted["event_id"]).json()
        assert detail["payload"]["request"] == {**command, "manual_additions": []}
        assert client.get(URL + "/missing/events/" + adopted["event_id"]).status_code == 404
        assert (
            client.get(
                URL + "/" + discovery_id + "/events",
                params={"cursor": "eyJkaXNjb3ZlcnkiOiJvdGhlciIsImFmdGVyIjoxfQ=="},
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    "fault", ["missing", "foreign", "hash", "silent_edit", "unexplained", "project", "source_roles"]
)
def test_bad_adoption_has_zero_formal_side_effects(impact_app, fault):
    with impact_app() as (client, service, body, _, original):
        discovery_id, state = discover(client, body)
        command = adoption(state, original)
        if fault == "missing":
            command["dispositions"].pop()
        elif fault == "foreign":
            command["dispositions"][0]["candidate_id"] = "candidate-from-another-run"
        elif fault == "hash":
            command["catalog_hash"] = "0" * 64
        elif fault == "silent_edit":
            command["destination"]["request"]["targets"][0]["checks"][0]["behavior"] = (
                "偷偷更改建议"
            )
        elif fault == "unexplained":
            command["dispositions"] = [
                c for c in command["dispositions"] if c.get("target_index") != 1
            ]
        elif fault == "project":
            with service.store.database.factory() as session:
                old = session.get(Project, "project-test")
                other = Path(old.repository_path).with_name("other-source")
                shutil.copytree(old.repository_path, other)
                session.add(Project(id="other-project", name="Other", repository_path=str(other)))
                session.commit()
            command["destination"]["request"]["project_id"] = "other-project"
        else:
            command["destination"]["request"]["source"]["groups"].append(
                dict(role="contract", paths=["examples/client.py"])
            )
        response = post(client, URL + "/" + discovery_id + "/adoptions", command)
        assert response.status_code == 409, response.text
        assert counts(service) == (0, 0, 0, 0)


def test_edit_and_manual_addition_are_not_counted_as_model_discovery(impact_app):
    with impact_app() as (client, service, body, _, original):
        discovery_id, state = discover(client, body)
        command = adoption(state, original)
        selected = next(c for c in command["dispositions"] if c["disposition"] == "take")
        selected.update(disposition="edit", reason="人工明确更正检查描述")
        target = command["destination"]["request"]["targets"][selected["target_index"]]
        target["checks"][0]["behavior"] = "人工更正后的字段检查"
        manual = copy.deepcopy(target)
        manual.update(source_path="tests/test_create_export.py")
        command["destination"]["request"]["targets"].append(manual)
        command["manual_additions"] = [dict(target_index=2, reason="人工另外采用测试目标")]
        response = post(client, URL + "/" + discovery_id + "/adoptions", command)
        assert response.status_code == 202, response.text
        with service.store.read() as conn:
            frozen = service.verifications.input(
                conn, response.json()["review_id"], response.json()["input_revision_id"]
            )
        assert len(frozen["impact_origin"]["candidate_mapping"]) == 2
        assert frozen["impact_origin"]["manual_additions"] == command["manual_additions"]


@pytest.mark.parametrize(
    "fault",
    [
        "unread",
        "outside",
        "invented_identity",
        "rule_as_observation",
        "duplicate",
        "wrong_role",
        "unprojected_observation",
    ],
)
def test_illegal_actions_are_rejected_after_one_correction(impact_app, fault):
    def transform(action, data):
        catalog = data["source_catalog"]["items"]
        if fault in ("unread", "outside", "invented_identity", "rule_as_observation"):
            if fault == "unread":
                source = next(s for s in catalog if s["path"] == "docs/api.md")
                action["reason"]["evidence_refs"] = [
                    dict(
                        kind="source",
                        source_ref=dict(source_id=source["source_id"], selector=dict(kind="full")),
                    )
                ]
            elif fault == "outside":
                action["arguments"]["source_id"] = "source-not-allowed"
            elif fault == "invented_identity":
                action["target_id"] = "fabricated-formal-target"
            else:
                action["reason"]["evidence_refs"] = [dict(kind="rule", adoption_id="not-a-rule")]
        elif action["action"] == "submit_candidates":
            if fault == "duplicate":
                action["candidates"].append(copy.deepcopy(action["candidates"][0]))
            elif fault == "wrong_role":
                action["candidates"][0]["artifact_role"] = "decision_reference"
            else:
                action["candidates"][0]["observation_refs"] = ["iobs-not-projected"]
        return action

    with impact_app(transform=transform) as (client, service, body, adapter, _):
        response = post(client, URL, body)
        state = terminal(client, URL + "/" + response.json()["discovery_id"])
        assert state["status"] == "failed"
        assert state["error_code"] == "ACTION_PROTOCOL_ERROR"
        assert state["catalog"] is None
        assert counts(service) == (0, 0, 0, 0)
        if fault in ("unread", "outside", "invented_identity", "rule_as_observation"):
            assert state["budget"]["tool_actions"] == 0
            assert len(adapter.requests) == 2


@pytest.mark.parametrize(
    "field,value",
    [("extra", 1), ("project_id", None), ("execution_profile_id", True), ("targets", [])],
)
def test_discovery_schema_rejects_before_persistence(impact_app, field, value):
    with impact_app(worker=False) as (client, service, body, _, _):
        body[field] = value
        assert post(client, URL, body).status_code == 422
        with service.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_impact_discoveries"
                ).scalar_one()
                == 0
            )


@pytest.mark.parametrize(
    "settings,usage,error,model_calls",
    [
        ({"context_characters": 1}, True, "BUDGET_EXHAUSTED", 0),
        ({"model_call_limit": 1}, True, "BUDGET_EXHAUSTED", 1),
        ({}, False, "USAGE_UNKNOWN", 1),
    ],
)
def test_discovery_hard_bounds_do_not_dispatch_an_extra_model_call(
    impact_app, settings, usage, error, model_calls
):
    with impact_app(impact_settings=settings, usage=usage) as (client, _, body, adapter, _):
        response = post(client, URL, body)
        state = terminal(client, URL + "/" + response.json()["discovery_id"])
        assert state["status"] == "failed" and state["error_code"] == error
        assert len(adapter.requests) == state["budget"]["model_calls"] == model_calls


@pytest.mark.parametrize("pause_kind", ["impact", "review"])
def test_timeout_holds_shared_slot_in_both_directions_and_late_result_is_not_accepted(
    impact_app, pause_kind
):
    release = threading.Event()
    with impact_app(
        pause=release,
        pause_kind=pause_kind,
        impact_settings=dict(model_timeout_seconds=0.05),
        review_settings=dict(model_timeout_seconds=0.05),
    ) as (client, service, body, adapter, original):
        if pause_kind == "impact":
            first = post(client, URL, body, "first").json()
            first_path = URL + "/" + first["discovery_id"]
        else:
            first = post(client, REVIEW, original, "first").json()
            first_path = REVIEW + "/" + first["review_id"]
        assert adapter.entered.wait(2)
        state = terminal(client, first_path)
        assert state["status"] == "failed"
        if pause_kind == "impact":
            second = post(client, REVIEW, original, "second").json()
            second_path = REVIEW + "/" + second["review_id"]
        else:
            second = post(client, URL, body, "second").json()
            second_path = URL + "/" + second["discovery_id"]
        time.sleep(0.08)
        assert client.get(second_path).json()["status"] == "queued"
        assert len(adapter.requests) == 1
        with service.store.read() as conn:
            gate = service.worker.dispatch_gate(conn)
        assert not gate["can_claim"] and gate["blocked_by"]
        release.set()
        terminal(client, second_path)
        assert client.get(first_path).json()["status"] == "failed"
        if pause_kind == "impact":
            assert client.get(first_path).json()["catalog"] is None


def test_failed_intent_persistence_dispatches_zero_requests(impact_app, monkeypatch):
    with impact_app() as (client, service, body, adapter, _):
        original_event = service.impacts.event

        def fault(conn, owner, kind, payload):
            if kind == "dispatch_intent":
                raise ReviewError("EVIDENCE_PERSISTENCE_FAILED", "意图保存故障", 503)
            return original_event(conn, owner, kind, payload)

        monkeypatch.setattr(service.impacts, "event", fault)
        response = post(client, URL, body)
        state = terminal(client, URL + "/" + response.json()["discovery_id"])
        assert state["status"] == "failed"
        assert state["budget"]["model_calls"] == 0 and not adapter.requests
        with service.store.read() as conn:
            runtime = service.store.row(conn, "SELECT * FROM contract_review_runtime WHERE id=1")
            assert runtime["slot_call_id"] is runtime["slot_discovery_call_id"] is None


def test_restart_interrupts_discovery_fences_old_owner_and_reconciles_only_proven_exit(
    impact_app, monkeypatch
):
    with impact_app(worker=False) as (client, service, body, _, _):
        old = SharedLedger(service)
        old.start()
        response = post(client, URL, body)
        discovery_id = response.json()["discovery_id"]
        context = old.claim()
        profile = context["frozen"]["execution_profile"]
        wire = dict(model=profile["model"], max_tokens=profile["max_output_tokens"], messages=[])
        call, instance = old.reserve_call(context, "analysis", wire, [])
        old.dispatch_started(context, call)
        new = SharedLedger(service)
        new.start()
        assert service.impacts.get(discovery_id)["status"] == "interrupted"
        assert new.claim() is None
        with pytest.raises(ReviewError, match="执行权"):
            old.fail(context, "STALE")
        monkeypatch.setattr(
            "specflow.contract_review.impact_ledger.original_process_exited", lambda process: True
        )
        new.impact.reconcile_dead_process()
        with service.store.read() as conn:
            row = service.store.row(
                conn, "SELECT * FROM contract_impact_calls WHERE id=:id", id=call
            )
            runtime = service.store.row(conn, "SELECT * FROM contract_review_runtime WHERE id=1")
        assert runtime["slot_discovery_call_id"] is None
        assert row["status"] == "UNKNOWN" and json.loads(row["body"])["result"] is None
        assert not new.settle_call(
            call, instance, quiesced=True, evidence="original_process_exited"
        )


def test_no_progress_is_bounded_but_one_empty_search_is_legal(impact_app):
    def repeat(action, data):
        return dict(
            schema_version="contract-impact-action.v1",
            action="tool_call",
            reason=action["reason"],
            tool="list_sources",
            arguments={},
        )

    with impact_app(transform=repeat) as (client, _, body, adapter, _):
        response = post(client, URL, body)
        state = terminal(client, URL + "/" + response.json()["discovery_id"])
        assert state["error_code"] == "NO_PROGRESS"
        assert len(adapter.requests) == state["budget"]["tool_actions"] == 3


def test_empty_search_can_be_followed_by_reads_and_valid_completion(impact_app):
    first = True

    def search(action, data):
        nonlocal first
        if first:
            first = False
            return dict(
                schema_version="contract-impact-action.v1",
                action="tool_call",
                reason=action["reason"],
                tool="search_sources",
                arguments=dict(
                    query="definitely-not-in-allowed-fixture",
                    source_ids=[data["source_catalog"]["items"][0]["source_id"]],
                ),
            )
        return action

    with impact_app(transform=search) as (client, _, body, _, _):
        _, state = discover(client, body)
        assert state["catalog"] is not None


def test_unknown_version_remains_unknown_until_explicit_human_edit(impact_app):
    def unknown(action, data):
        if action["action"] == "submit_candidates":
            for candidate in action["candidates"]:
                candidate.pop("api_version")
                candidate["unknowns"] = ["版本归属仍需人工明确"]
        return action

    with impact_app(transform=unknown) as (client, service, body, _, original):
        discovery_id, state = discover(client, body)
        assert all("api_version" not in c for c in state["catalog"]["candidates"])
        user_view = copy.deepcopy(state)
        for candidate in user_view["catalog"]["candidates"]:
            candidate["api_version"] = "v2"
        command = adoption(user_view, original)
        assert (
            post(
                client, URL + "/" + discovery_id + "/adoptions", command, "take-unknown"
            ).status_code
            == 409
        )
        for choice in command["dispositions"]:
            if choice["disposition"] == "take":
                choice.update(disposition="edit", reason="人工明确本次版本为v2，保留原未知记录")
        assert (
            post(client, URL + "/" + discovery_id + "/adoptions", command, "edit-known").status_code
            == 202
        )
        assert counts(service) == (1, 1, 1, 1)


def test_mock_http_wire_equals_discovery_projection(impact_app, controlled_adapter):
    import httpx

    from specflow.contract_review.provider import OpenAIReviewAdapter
    from specflow.llm.providers.config import OpenAICompatibleConfig

    logic = ImpactAdapter(controlled_adapter())
    actual = []

    def respond(request):
        payload = json.loads(request.content)
        actual.append(payload)
        result = logic.complete(payload)
        return httpx.Response(
            200,
            json=dict(
                model=result["model"],
                choices=[dict(message=dict(content=result["content"]))],
                usage=dict(prompt_tokens=3, completion_tokens=4),
            ),
        )

    adapter = OpenAIReviewAdapter(
        OpenAICompatibleConfig(
            "https://offline.invalid", "synthetic-test-only", "controlled-test", 45
        ),
        transport=httpx.MockTransport(respond),
        execution_mode="test",
    )
    with impact_app(
        adapter_override=adapter, impact_settings=dict(provider_binding=adapter.binding)
    ) as (client, service, body, _, _):
        discovery_id, _ = discover(client, body)
        with service.store.read() as conn:
            projected = [
                json.loads(row[0])["projection"]["payload"]
                for row in conn.execute(
                    text(
                        "SELECT body FROM contract_impact_calls WHERE discovery_id=:id AND "
                        "json_extract(body,'$.kind')='model'"
                    ),
                    dict(id=discovery_id),
                )
            ]
        assert sorted(map(digest, projected)) == sorted(map(digest, actual))


def test_discovery_routes_keep_authentication_and_query_boundaries(impact_app):
    with impact_app(worker=False) as (client, service, body, _, _):
        client.headers.clear()
        assert post(client, URL, body).status_code == 401
        client.headers["X-API-Key"] = "test-impact-key"
        assert post(client, URL + "?unknown=1", body).status_code == 422
        with service.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_impact_discoveries"
                ).scalar_one()
                == 0
            )
