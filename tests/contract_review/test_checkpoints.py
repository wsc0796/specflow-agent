"""HTTP checkpoints persist human decisions atomically and consume exact next input."""

import copy
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from specflow.contract_review.checkpoints import ResolutionBatch, RevisionRequest
from specflow.contract_review.common import ReviewError
from specflow.contract_review.profiles import dynamic_profile

URL = "/api/v1/contract-reviews"


class HumanAdapter:
    """Produce two bounded questions, then let the controlled fallback finish."""

    execution_mode = "test"

    def __init__(self, fallback, *, reask=False, later_work=None):
        self.fallback, self.reask = fallback, reask
        self.later_work = later_work

    def __getattr__(self, name):
        return getattr(self.fallback, name)

    def complete(self, payload):
        result = self.fallback.complete(payload)
        data = json.loads(payload["messages"][1]["content"])
        if "candidate_report" in data:
            return result
        action = json.loads(result["content"])
        report = action["report"]
        if not data["resolutions"] or self.reask:
            target = data["targets"][0]["target_id"]
            finding = report["findings"][0]["id"]
            report["questions"] = [
                {
                    "id": identifier,
                    "kind": kind,
                    "prompt": "请明确本次示例归属及缺失材料。",
                    "blocking": True,
                    "target_ids": [target],
                    "finding_ids": [finding],
                    "work_item_ids": [],
                    "rule_refs": [],
                    "evidence_refs": [],
                    "why_blocking": "缺少本次明确选择。",
                    "options": [
                        {"id": "v1", "label": "API v1", "consequence": "保留旧版字段。"},
                        {"id": "v2", "label": "API v2", "consequence": "按新版字段核对。"},
                    ],
                    "allowed_answer_types": ["select", "clarify", "mark_insufficient"],
                }
                for identifier, kind in (
                    ("q_scope", "scope_choice"),
                    ("q_material", "missing_evidence"),
                )
            ]
        if data["resolutions"] and self.later_work:
            target, finding = data["targets"][0]["target_id"], report["findings"][0]["id"]
            ready = self.later_work == "ready"
            report["work_items"] = [
                {
                    "id": "w",
                    "title": "取得获准证据",
                    "finding_ids": [finding],
                    "target_ids": [target],
                    "rule_refs": [],
                    "source_refs": [],
                    "handling_intent": {"kind": "obtain_evidence", "text": "等待真实材料。"},
                    "proposed_scope": {
                        "include": [{"artifact_role": "documentation", "paths": ["docs/api.md"]}],
                        "exclude": [],
                    },
                    "depends_on": [],
                    "readiness": self.later_work,
                    "blockers": []
                    if ready
                    else [
                        {
                            "code": "missing_evidence",
                            "reason": "缺少获准材料。",
                            "refs": [{"kind": "target", "id": target}],
                        }
                    ],
                    "acceptance_ids": ["a"] if ready else [],
                    "execution_authorized": False,
                }
            ]
            if ready:
                report["acceptance_items"] = [
                    {
                        "id": "a",
                        "work_item_id": "w",
                        "finding_ids": [finding],
                        "target_ids": [target],
                        "rule_refs": [],
                        "source_refs": [],
                        "given": "已有材料。",
                        "when": "核对。",
                        "then": "取得证据。",
                        "verification_method": {
                            "kind": "static_review",
                            "procedure": "读取获准材料。",
                            "required_environment": "密封快照",
                        },
                        "expected_evidence": ["材料原文"],
                        "evidence_refs": [],
                        "execution_status": "NOT_RUN",
                    }
                ]
        result["content"] = json.dumps(action, ensure_ascii=False)
        return result


def create(client, body, key="review"):
    response = client.post(URL, json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()["review_id"]


def terminal(client, review_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = client.get(f"{URL}/{review_id}").json()
        if state["status"] not in ("queued", "running"):
            return state
        time.sleep(0.01)
    pytest.fail(str(state))


def waiting(client, body):
    review_id = create(client, body)
    state = terminal(client, review_id)
    assert state["status"] == "awaiting_decision", state
    report = client.get(f"{URL}/{review_id}/report").json()
    return review_id, state, report


def answer(question="q_scope", kind="clarify", value="本轮明确采用 API v2。"):
    result = {"question_id": question, "scope": "this_review", "answer_type": kind}
    result[{"select": "option_id", "clarify": "text", "mark_insufficient": "reason"}[kind]] = value
    return result


def batch(state, report, answers=None):
    return {
        "expected_version": state["version"],
        "input_revision_id": report["input_revision_id"],
        "report_revision_id": report["report_revision_id"],
        "answers": answers if answers is not None else [answer()],
        "actor_label": "自填维护者标签",
    }


def post(client, review_id, value, key="answers", endpoint="resolution-batches"):
    return client.post(
        f"{URL}/{review_id}/{endpoint}", json=value, headers={"Idempotency-Key": key}
    )


def revision(state, **changes):
    return {
        "expected_version": state["version"],
        "base_input_revision_id": state["current_input_revision_id"],
        "change_reason": "显式更正本次审查输入。",
        **changes,
    }


def footprint(domain, review_id):
    with domain.store.read() as conn:
        row = domain.require_review(conn, review_id)
        return (
            row["version"],
            row["status"],
            row["current_input_id"],
            row["current_report_id"],
            row["event_seq"],
            *[
                domain.store.row(
                    conn, f"SELECT count(*) AS n FROM {table} WHERE review_id=:id", id=review_id
                )["n"]
                for table in (
                    "contract_review_resolutions",
                    "contract_review_inputs",
                    "contract_review_jobs",
                )
            ],
            domain.store.row(
                conn,
                "SELECT body FROM contract_review_budget_accounts WHERE review_id=:id",
                id=review_id,
            )["body"],
        )


def frozen(domain, review_id, input_id):
    with domain.store.read() as conn:
        return domain.verifications.input(conn, review_id, input_id)


@pytest.mark.parametrize(
    "kind,value", [("select", "v2"), ("clarify", "原文尾部"), ("mark_insufficient", "缺少材料")]
)
def test_answer_discriminated_union_keeps_original_fields(kind, value):
    raw = {
        "expected_version": 1,
        "input_revision_id": "ir",
        "report_revision_id": "rr",
        "answers": [answer(kind=kind, value=value)],
    }
    assert (
        ResolutionBatch.model_validate(raw).model_dump(exclude_none=True)["answers"]
        == raw["answers"]
    )


@pytest.mark.parametrize(
    "bad",
    [
        "bool_version",
        "float_version",
        "null",
        "unknown",
        "missing_option",
        "foreign_field",
        "wrong_scope",
        "empty_text",
        "long_text",
        "duplicate",
        "too_many",
    ],
)
def test_answer_http_schema_rejects_before_any_side_effect(review_client, bad):
    client, domain, body = review_client
    review_id = create(client, body)
    raw = {
        "expected_version": 1,
        "input_revision_id": "ir",
        "report_revision_id": "rr",
        "answers": [answer()],
    }
    if bad == "bool_version":
        raw["expected_version"] = True
    elif bad == "float_version":
        raw["expected_version"] = 1.0
    elif bad == "null":
        raw["actor_label"] = None
    elif bad == "unknown":
        raw["approve_project_rule"] = True
    elif bad == "missing_option":
        raw["answers"] = [{"question_id": "q", "scope": "this_review", "answer_type": "select"}]
    elif bad == "foreign_field":
        raw["answers"][0]["option_id"] = "v2"
    elif bad == "wrong_scope":
        raw["answers"][0]["scope"] = "project"
    elif bad == "empty_text":
        raw["answers"][0]["text"] = ""
    elif bad == "long_text":
        raw["answers"][0]["text"] = "x" * 4001
    elif bad == "duplicate":
        raw["answers"] *= 2
    else:
        raw["answers"] = [answer(question=f"q{i}") for i in range(21)]
    before = footprint(domain, review_id)
    assert post(client, review_id, raw).status_code == 422
    assert footprint(domain, review_id) == before


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"expected_version": True},
        {"review_directives": None},
        {"verification_evidence_ids": ["e", "e"]},
        {"supersede_resolution_ids": ["r"]},
        {"unknown": True},
    ],
)
def test_revision_schema_rejects_ambiguous_or_incomplete_changes(changes):
    raw = {
        "expected_version": 1,
        "base_input_revision_id": "ir",
        "change_reason": "更正。",
        **changes,
    }
    with pytest.raises(ValidationError):
        RevisionRequest.model_validate(raw)


def test_partial_answer_persists_and_last_answer_creates_one_input_and_job(
    running_app, controlled_adapter
):
    pause = threading.Event()
    adapter = HumanAdapter(controlled_adapter(pauses={3: pause}))
    with running_app(adapter, timeout=5) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        original_input = frozen(domain, review_id, report["input_revision_id"])
        first_body = batch(state, report)
        first = post(client, review_id, first_body)
        assert first.status_code == 200, first.text
        assert first.json()["remaining_blocking_question_ids"] == ["q_material"]
        assert first.json()["job_id"] is None
        assert len(adapter.requests) == 2
        current = client.get(f"{URL}/{review_id}").json()
        assert current["status"] == "awaiting_decision"
        assert current["remaining_blocking_question_ids"] == ["q_material"]
        assert current["resolutions"][0]["answer"]["text"] == first_body["answers"][0]["text"]
        assert client.get(f"{URL}/{review_id}/report").json() == report
        replay = post(client, review_id, first_body)
        assert replay.status_code == 200 and replay.json() == first.json()
        changed = copy.deepcopy(first_body)
        changed["answers"][0]["text"] = "不同的人工解释。"
        assert post(client, review_id, changed).json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
        duplicate = post(client, review_id, batch(current, report), "already-answered")
        assert duplicate.json()["error"]["code"] == "QUESTION_ALREADY_RESOLVED"
        last_body = batch(
            current, report, [answer("q_material", "mark_insufficient", "没有更多获准材料。")]
        )
        last = post(client, review_id, last_body, "last-answer")
        assert last.status_code == 202, last.text
        assert adapter.entered[3].wait(3)
        next_state = client.get(f"{URL}/{review_id}").json()
        assert next_state["status"] in ("queued", "running")
        assert (
            next_state["current_report_revision_id"] is None and not next_state["report_available"]
        )
        assert client.get(f"{URL}/{review_id}/report").status_code == 404
        old_target = {**first_body, "expected_version": next_state["version"]}
        assert (
            post(client, review_id, old_target, "while-running").json()["error"]["code"]
            == "REVIEW_BUSY"
        )
        assert (
            client.get(
                f"{URL}/{review_id}/report",
                params={"report_revision_id": report["report_revision_id"]},
            ).json()
            == report
        )
        next_input = frozen(domain, review_id, last.json()["input_revision_id"])
        assert next_input["snapshot_id"] == original_input["snapshot_id"]
        assert next_input["target_manifest"] == original_input["target_manifest"]
        assert next_input["check_manifest"] == original_input["check_manifest"]
        assert len(next_input["resolutions"]) == 2
        assert next_input["execution_profile"] == original_input["execution_profile"]
        replay = post(client, review_id, last_body, "last-answer")
        assert replay.status_code == 202 and replay.json() == last.json()
        with domain.store.read() as conn:
            assert (
                domain.store.row(
                    conn,
                    "SELECT count(*) AS n FROM contract_review_inputs WHERE review_id=:id",
                    id=review_id,
                )["n"]
                == 2
            )
            assert (
                domain.store.row(
                    conn,
                    "SELECT count(*) AS n FROM contract_review_jobs WHERE review_id=:id",
                    id=review_id,
                )["n"]
                == 2
            )
        pause.set()
        final = terminal(client, review_id)
        assert final["status"] == "completed_degraded", final
        assert final["budget"]["model_calls"] == 4


def test_partial_answers_are_reconstructed_by_a_fresh_service(running_app, controlled_adapter):
    from specflow.contract_review.service import ReviewService
    from specflow.contract_review.store import ReviewStore
    from specflow.db import Database

    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        assert post(client, review_id, batch(state, report)).status_code == 200
        domain.worker.close()
        database = Database(str(domain.store.database.engine.url))
        try:
            restored = ReviewService(ReviewStore(database), domain.snapshot_reader, domain.profiles)
            current = restored.get(review_id)
            assert current["status"] == "awaiting_decision"
            assert current["remaining_blocking_question_ids"] == ["q_material"]
            assert current["resolutions"][0]["question_id"] == "q_scope"
            assert current["resolutions"][0]["actor_subject"] == "shared-service"
            assert restored.report(review_id) == report
        finally:
            database.engine.dispose()


def test_cross_review_input_and_report_cannot_receive_answers(running_app, controlled_adapter):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        first, _, _ = waiting(client, body)
        second = create(client, body, "second")
        second_state = terminal(client, second)
        second_report = client.get(f"{URL}/{second}/report").json()
        before = footprint(domain, first), footprint(domain, second)
        response = post(client, first, batch(second_state, second_report))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert (footprint(domain, first), footprint(domain, second)) == before


def test_waiting_review_releases_worker_for_another_review(running_app, controlled_adapter):
    adapter = HumanAdapter(controlled_adapter())
    with running_app(adapter) as (client, _, body):
        first, _, _ = waiting(client, body)
        second = create(client, body, "second")
        assert terminal(client, second)["status"] == "awaiting_decision"
        assert client.get(f"{URL}/{first}").json()["status"] == "awaiting_decision"
        assert len(adapter.requests) == 4


@pytest.mark.parametrize(
    "bad", ["question", "type", "option", "version", "report", "input", "mixed"]
)
def test_invalid_batch_is_atomic_and_preserves_current_report(running_app, controlled_adapter, bad):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        raw = batch(state, report)
        expected = "RESOURCE_NOT_FOUND"
        if bad == "question":
            raw["answers"][0]["question_id"] = "another-report-question"
        elif bad == "type":
            raw["answers"][0] = answer(kind="select", value="v2")
            with domain.store.transaction() as conn:
                # Exercise a persisted question allowing clarify only.
                stored = copy.deepcopy(report)
                stored["payload"]["questions"][0]["allowed_answer_types"] = ["clarify"]
                domain.store.execute(
                    conn,
                    "UPDATE contract_review_reports SET body=:body WHERE id=:id",
                    id=report["report_revision_id"],
                    body=json.dumps(stored),
                )
            expected = "INVALID_ANSWER"
        elif bad == "option":
            raw["answers"][0] = answer(kind="select", value="not-an-option")
            expected = "INVALID_ANSWER"
        elif bad == "version":
            raw["expected_version"] -= 1
            expected = "VERSION_CONFLICT"
        elif bad == "report":
            raw["report_revision_id"] = "missing-report"
        elif bad == "input":
            raw["input_revision_id"] = "missing-input"
        else:
            raw["answers"].append(answer("missing-question"))
        before = footprint(domain, review_id)
        response = post(client, review_id, raw)
        assert response.json()["error"]["code"] == expected, response.text
        assert footprint(domain, review_id) == before


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("budget", "REVIEW_BUDGET_EXHAUSTED"),
        ("profile", "RETRY_PROFILE_UNAVAILABLE"),
        ("queue", "QUEUE_FULL"),
        ("event", "DEPENDENCY_UNAVAILABLE"),
    ],
)
def test_last_batch_admission_or_persistence_failure_rolls_back_everything(
    running_app, controlled_adapter, monkeypatch, failure, expected
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        if failure == "budget":
            with domain.store.transaction() as conn:
                account = json.loads(
                    domain.store.row(
                        conn,
                        "SELECT body FROM contract_review_budget_accounts WHERE review_id=:id",
                        id=review_id,
                    )["body"]
                )
                account["model_calls"] = account["grant"]["model_calls"]
                domain.store.execute(
                    conn,
                    "UPDATE contract_review_budget_accounts SET body=:body WHERE review_id=:id",
                    id=review_id,
                    body=json.dumps(account),
                )
        elif failure == "profile":
            domain.profiles.clear()
        elif failure == "queue":
            monkeypatch.setattr(
                domain,
                "capacity",
                lambda *args, **kwargs: (_ for _ in ()).throw(
                    ReviewError("QUEUE_FULL", "controlled full", 429)
                ),
            )
        else:
            original = domain.store.event

            def fail(conn, review, input_id, job, kind, payload, **links):
                if kind == "resolutions_recorded":
                    raise ReviewError("DEPENDENCY_UNAVAILABLE", "controlled failure", 503)
                return original(conn, review, input_id, job, kind, payload, **links)

            monkeypatch.setattr(domain.store, "event", fail)
        before = footprint(domain, review_id)
        raw = batch(state, report, [answer(), answer("q_material")])
        response = post(client, review_id, raw)
        assert response.json()["error"]["code"] == expected, response.text
        assert footprint(domain, review_id) == before


def test_concurrent_last_batches_only_one_wins_cas(running_app, controlled_adapter):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        domain.worker.close()
        raw = batch(state, report, [answer(), answer("q_material")])
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda key: post(client, review_id, raw, key), ["a", "b"]))
        assert sorted(response.status_code for response in responses) == [202, 409]
        with domain.store.read() as conn:
            assert (
                domain.store.row(
                    conn,
                    "SELECT count(*) AS n FROM contract_review_resolutions WHERE review_id=:id",
                    id=review_id,
                )["n"]
                == 2
            )
            assert (
                domain.store.row(
                    conn,
                    "SELECT count(*) AS n FROM contract_review_jobs WHERE review_id=:id",
                    id=review_id,
                )["n"]
                == 2
            )


@pytest.mark.parametrize("dynamic", [False, True])
@pytest.mark.parametrize(
    "text", ["前文" * 1800 + "必须采用 API v1 尾部", "前文" * 1800 + "必须采用 API v2 尾部"]
)
def test_full_human_answer_reaches_next_analysis_and_fixed_review(
    running_app, controlled_adapter, test_profile, dynamic, text
):
    if dynamic:
        test_profile.clear()
        test_profile.update(
            dynamic_profile("controlled-test-v1", "controlled-test", delegation=False)
        )
    adapter = HumanAdapter(controlled_adapter())
    with running_app(adapter) as (client, _, body):
        review_id, state, report = waiting(client, body)
        response = post(
            client, review_id, batch(state, report, [answer(value=text), answer("q_material")])
        )
        assert response.status_code == 202, response.text
        assert terminal(client, review_id)["status"] == "completed_degraded"
        next_requests = [
            json.loads(payload["messages"][1]["content"]) for payload in adapter.requests[2:]
        ]
        assert len(next_requests) == 2
        for data in next_requests:
            assert data["resolutions"][0]["answer"]["text"] == text


@pytest.mark.parametrize("dynamic", [False, True])
def test_reask_after_mark_insufficient_stops_as_protocol_failure(
    running_app, controlled_adapter, test_profile, dynamic
):
    if dynamic:
        test_profile.clear()
        test_profile.update(
            dynamic_profile("controlled-test-v1", "controlled-test", delegation=False)
        )
    adapter = HumanAdapter(controlled_adapter(), reask=True)
    with running_app(adapter) as (client, _, body):
        review_id, state, report = waiting(client, body)
        raw = batch(
            state, report, [answer(), answer("q_material", "mark_insufficient", "没有新增材料。")]
        )
        assert post(client, review_id, raw).status_code == 202
        final = terminal(client, review_id)
        assert final["status"] == "failed", final
        assert final["error_code"] == "ACTION_PROTOCOL_ERROR"


@pytest.mark.parametrize("readiness", ["ready", "not_ready"])
def test_mark_insufficient_keeps_related_work_not_ready(running_app, controlled_adapter, readiness):
    adapter = HumanAdapter(controlled_adapter(), later_work=readiness)
    with running_app(adapter) as (client, _, body):
        review_id, state, report = waiting(client, body)
        raw = batch(
            state, report, [answer(), answer("q_material", "mark_insufficient", "缺少获准材料。")]
        )
        assert post(client, review_id, raw).status_code == 202
        final = terminal(client, review_id)
        if readiness == "ready":
            assert final["status"] == "failed" and final["error_code"] == "ACTION_PROTOCOL_ERROR", (
                final
            )
        else:
            assert final["status"] == "completed_degraded", final
            result = client.get(f"{URL}/{review_id}/report").json()
            assert result["payload"]["work_items"][0]["readiness"] == "not_ready"


def test_partial_answer_can_be_corrected_by_revision_and_old_record_remains(
    running_app, controlled_adapter
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        accepted = post(client, review_id, batch(state, report))
        assert accepted.status_code == 200
        resolution_id = accepted.json()["accepted_resolution_ids"][0]
        current = client.get(f"{URL}/{review_id}").json()
        domain.worker.close()
        response = post(
            client,
            review_id,
            revision(
                current,
                supersede_resolution_ids=[resolution_id],
                review_directives=["更正上次答案，本次按 v1 核对。"],
            ),
            "correction",
            "revisions",
        )
        assert response.status_code == 202, response.text
        next_input = frozen(domain, review_id, response.json()["input_revision_id"])
        assert next_input["resolutions"] == []
        assert next_input["resolution_adoptions"][0]["status"] == "superseded"
        with domain.store.read() as conn:
            original = domain.store.row(
                conn, "SELECT body FROM contract_review_resolutions WHERE id=:id", id=resolution_id
            )
            assert json.loads(original["body"])["answer"]["text"] == "本轮明确采用 API v2。"


def test_request_revision_reuses_sealed_bytes_preserves_checks_and_keeps_partial_answer(
    running_app, controlled_adapter, monkeypatch
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        assert post(client, review_id, batch(state, report)).status_code == 200
        state = client.get(f"{URL}/{review_id}").json()
        previous = frozen(domain, review_id, state["current_input_revision_id"])
        domain.worker.close()
        monkeypatch.setattr(
            domain.snapshot_reader, "prepare", lambda *args: pytest.fail("unchanged source reread")
        )
        response = post(
            client,
            review_id,
            revision(state, request=body["request"] + " 只核对当前范围。"),
            "revision",
            "revisions",
        )
        assert response.status_code == 202, response.text
        next_input = frozen(domain, review_id, response.json()["input_revision_id"])
        assert next_input["snapshot_id"] == previous["snapshot_id"]
        assert next_input["target_manifest"] == previous["target_manifest"]
        assert next_input["check_manifest"] == previous["check_manifest"]
        assert len(next_input["resolutions"]) == 1
        assert next_input["resolution_adoptions"][0]["status"] == "adopted"
        assert client.get(f"{URL}/{review_id}").json()["current_report_revision_id"] is None


def test_new_source_revision_seals_new_commit_and_excludes_old_answer(
    running_app, controlled_adapter, git_repo
):
    root, git, _ = git_repo
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        assert post(client, review_id, batch(state, report)).status_code == 200
        current = client.get(f"{URL}/{review_id}").json()
        previous = frozen(domain, review_id, current["current_input_revision_id"])
        path = root / "docs/api.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nNew evidence.\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "New explicit material")
        source = {**body["source"], "commit_sha": git("rev-parse", "HEAD")}
        domain.worker.close()
        raw = revision(current, source=source)
        response = post(client, review_id, raw, "source-revision", "revisions")
        assert response.status_code == 202, response.text
        next_input = frozen(domain, review_id, response.json()["input_revision_id"])
        assert next_input["snapshot_id"] != previous["snapshot_id"]
        assert next_input["commit_sha"] == source["commit_sha"]
        assert next_input["resolutions"] == []
        assert next_input["resolution_adoptions"][0]["status"] == "excluded"
        replay = post(client, review_id, raw, "source-revision", "revisions")
        assert replay.status_code == 202 and replay.json() == response.json()


def test_source_revision_rolls_back_snapshot_capacity_and_job_after_event_failure(
    running_app, controlled_adapter, git_repo, monkeypatch
):
    root, git, _ = git_repo
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, _ = waiting(client, body)
        domain.worker.close()
        path = root / "docs/api.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nNew evidence.\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "New explicit material")
        raw = revision(state, source={**body["source"], "commit_sha": git("rev-parse", "HEAD")})

        def storage():
            with domain.store.read() as conn:
                return (
                    tuple(
                        conn.exec_driver_sql(
                            "SELECT snapshot_bytes,record_bytes FROM contract_review_capacity"
                        ).one()
                    ),
                    conn.exec_driver_sql(
                        "SELECT count(*) FROM contract_review_snapshots"
                    ).scalar_one(),
                    conn.exec_driver_sql(
                        "SELECT count(*) FROM contract_review_source_blobs"
                    ).scalar_one(),
                    conn.exec_driver_sql(
                        "SELECT count(*) FROM contract_review_idempotency"
                    ).scalar_one(),
                )

        original = domain.store.event

        def fail(conn, review, input_id, job, kind, payload, **links):
            if kind == "input_revised":
                raise ReviewError("DEPENDENCY_UNAVAILABLE", "controlled final event failure", 503)
            return original(conn, review, input_id, job, kind, payload, **links)

        before = footprint(domain, review_id), storage()
        monkeypatch.setattr(domain.store, "event", fail)
        response = post(client, review_id, raw, "rollback-source", "revisions")
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
        assert (footprint(domain, review_id), storage()) == before


@pytest.mark.parametrize(
    "change", ["same_request", "same_ruleset", "same_profile", "same_evidence"]
)
def test_noop_revision_is_rejected_without_side_effects(running_app, controlled_adapter, change):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, _ = waiting(client, body)
        patch = {
            "same_request": {"request": body["request"]},
            "same_ruleset": {"ruleset_usage": {"mode": "none"}},
            "same_profile": {"execution_profile_id": body["execution_profile_id"]},
            "same_evidence": {"verification_evidence_ids": []},
        }[change]
        before = footprint(domain, review_id)
        response = post(client, review_id, revision(state, **patch), "noop", "revisions")
        assert response.status_code == 409, response.text
        assert footprint(domain, review_id) == before


def test_revision_directive_is_preserved_in_both_model_roles(running_app, controlled_adapter):
    adapter = HumanAdapter(controlled_adapter())
    with running_app(adapter) as (client, _, body):
        review_id, state, report = waiting(client, body)
        assert (
            post(
                client, review_id, batch(state, report, [answer(), answer("q_material")])
            ).status_code
            == 202
        )
        state = terminal(client, review_id)
        directive = "指令原文" * 700 + "尾部：保留 v1 差异。"
        response = post(
            client,
            review_id,
            revision(state, review_directives=[directive]),
            "directive",
            "revisions",
        )
        assert response.status_code == 202, response.text
        assert terminal(client, review_id)["status"] == "completed_degraded"
        for payload in adapter.requests[-2:]:
            assert json.loads(payload["messages"][1]["content"])["review_directives"] == [directive]


def test_new_mutation_endpoints_require_auth_key_and_reject_unknown_query(review_client):
    client, domain, body = review_client
    review_id = create(client, body)
    for endpoint, raw in (
        (
            "resolution-batches",
            {
                "expected_version": 1,
                "input_revision_id": "ir",
                "report_revision_id": "rr",
                "answers": [answer()],
            },
        ),
        (
            "revisions",
            {
                "expected_version": 1,
                "base_input_revision_id": "ir",
                "change_reason": "明确更正。",
                "review_directives": ["本次指令。"],
            },
        ),
    ):
        before = footprint(domain, review_id)
        client.headers.pop("X-API-Key")
        assert post(client, review_id, raw, endpoint=endpoint).status_code == 401
        client.headers["X-API-Key"] = "test-contract-key"
        assert client.post(f"{URL}/{review_id}/{endpoint}", json=raw).status_code == 422
        assert (
            client.post(
                f"{URL}/{review_id}/{endpoint}?unknown=1",
                json=raw,
                headers={"Idempotency-Key": "query"},
            ).status_code
            == 422
        )
        assert footprint(domain, review_id) == before
