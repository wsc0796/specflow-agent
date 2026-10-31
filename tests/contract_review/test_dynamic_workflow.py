"""Dynamic routing/delegation contracts through the actual HTTP/worker/DB chain."""

import copy
import json
import threading
import time
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity
from specflow.contract_review.common import ReviewError
from specflow.contract_review.dynamic_context import RunState
from specflow.contract_review.dynamic_ledger import DynamicLedger
from specflow.contract_review.profiles import dynamic_profile
from specflow.contract_review.provider import OpenAIReviewAdapter, ProviderFailure
from specflow.contract_review.snapshot_tools import SnapshotTools
from specflow.db import Project
from specflow.llm.providers.config import OpenAICompatibleConfig
from specflow.main import create_app

URL = "/api/v1/contract-reviews"


def reason(gap="读取所选片段"):
    return {"gap": gap, "evidence_refs": [], "expected_information": "取得有界证据"}


def read_action(data, path, *, child=False):
    item = next(item for item in data["source_catalog"]["items"] if item["path"] == path)
    return {
        "schema_version": "contract-review-child-action.v1"
        if child
        else "contract-review-action.v2.1",
        "action": "tool_call",
        "reason": reason(),
        "tool": "read_source",
        "arguments": {
            "source_id": item["source_id"],
            "start_line": 1,
            "end_line": min(200, item["line_count"]),
        },
    }


class ScriptedAdapter:
    execution_mode = "test"

    def __init__(self, fallback, mode="direct", *, disposition="adopted"):
        self.fallback, self.mode, self.disposition = fallback, mode, disposition
        self.requests = []
        self.pause = None
        self.entered = threading.Event()
        self.paused = False
        self.failure_once = None
        self.failed_once = False

    def complete(self, payload):
        self.requests.append(copy.deepcopy(payload))
        if self.failure_once and not self.failed_once:
            self.failed_once = True
            raise self.failure_once
        data = json.loads(payload["messages"][1]["content"])
        if "candidate_report" in data:
            return self.fallback.complete(payload)
        if "capability_id" in data:
            if self.pause and not self.paused:
                self.paused = True
                self.entered.set()
                assert self.pause.wait(10)
            if self.mode == "nested":
                result = {
                    "schema_version": "contract-review-child-action.v1",
                    "action": "delegate_task",
                }
            elif not data["observations"]:
                result = read_action(data, "docs/api.md", child=True)
            else:
                result = {
                    "schema_version": "contract-review-child-action.v1",
                    "action": "submit_report",
                    "reason": reason("子任务返回"),
                    "report": {
                        "schema_version": "contract-review-child-result.v1",
                        "status": "insufficient",
                        "findings": [],
                        "evidence_refs": [
                            {
                                "kind": "observation",
                                "observation_id": data["observations"][0]["observation_id"],
                            }
                        ],
                        "limitations": ["受控替身不进行业务语义判分。"],
                        "unresolved_gaps": ["需要父方形成报告。"],
                    },
                }
        elif self.mode == "invalid_tool":
            result = read_action(data, "docs/api.md")
            result["arguments"]["command"] = "write private file"
        elif self.mode == "repeat" or self.mode == "direct" and not data["observations"]:
            result = read_action(data, "docs/api.md")
        elif self.mode in ("delegate", "nested", "missing_review") and not data.get(
            "child_results"
        ):
            item = next(
                item for item in data["source_catalog"]["items"] if item["path"] == "docs/api.md"
            )
            rule = next(
                item
                for item in data["adoption_records"]
                if item["matched_target"].get("source_path") == "docs/api.md"
            )
            result = {
                "schema_version": "contract-review-action.v2.1",
                "action": "delegate_task",
                "reason": reason("文档取证缺口"),
                "capability_id": "docs_examples_alignment.v1",
                "objective": "只读取允许的文档片段。",
                "allowed_material_refs": [
                    {
                        "kind": "source",
                        "source_ref": {
                            "source_id": item["source_id"],
                            "selector": {"kind": "full"},
                        },
                    },
                    {"kind": "rule", "adoption_id": rule["adoption_id"]},
                ],
                "expected_evidence": ["文档原文"],
                "result_schema": "contract-review-child-result.v1",
            }
        else:
            result = json.loads(self.fallback.complete(payload)["content"])
            if data.get("child_results"):
                reviews = data.get("child_result_reviews") or [
                    {
                        "child_result_ref": item["child_result_ref"],
                        "disposition": "rejected"
                        if item["result"]["status"] == "failed"
                        else self.disposition,
                        "reason": "采用已读取的证据片段；排除业务正确性推断，仍保留未完成项。",
                    }
                    for item in data["child_results"]
                ]
                if self.mode != "missing_review":
                    result["child_result_reviews"] = reviews
                result["report"]["adopted_child_result_refs"] = reviews
        return {
            "content": json.dumps(result, ensure_ascii=False),
            "model": payload["model"],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }


@pytest.fixture
def dynamic_app(tmp_path, git_repo):
    root, _, body = git_repo

    @contextmanager
    def start(adapter, *, delegation=True, patch=None):
        profile = dynamic_profile(
            "dynamic-test",
            "controlled-test",
            delegation=delegation,
            provider_binding=getattr(adapter, "binding", None),
        )
        profile.update(patch or {})
        app = create_app(
            f"sqlite:///{(tmp_path / 'dynamic.sqlite').as_posix()}",
            tmp_path / "artifacts",
            ApiSecurity(api_key="test-key", allowed_repository_roots=(str(tmp_path),)),
            contract_review_profiles={profile["profile_id"]: profile},
            contract_review_adapter=adapter,
        )
        with TestClient(app) as client:
            with app.state.database.factory() as session:
                session.add(Project(id="project-test", name="Fixture", repository_path=str(root)))
                session.commit()
            client.headers["X-API-Key"] = "test-key"
            try:
                yield client, app.state.contract_reviews, copy.deepcopy(body)
            finally:
                if getattr(adapter, "pause", None):
                    adapter.pause.set()

    return start


def submit(client, body, key="one"):
    response = client.post(URL, json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()


def terminal(client, review_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = client.get(URL + "/" + review_id).json()
        if state["status"] not in ("queued", "running"):
            return state
        time.sleep(0.01)
    pytest.fail(str(state))


def mutate_adapter(adapter, transform):
    original = adapter.complete

    def complete(payload):
        result = original(payload)
        action = json.loads(result["content"])
        data = json.loads(payload["messages"][1]["content"])
        transform(action, data)
        result["content"] = json.dumps(action, ensure_ascii=False)
        return result

    adapter.complete = complete


def test_dynamic_direct_route_reads_only_after_action_and_needs_no_child(
    dynamic_app, controlled_adapter
):
    adapter = ScriptedAdapter(controlled_adapter())
    with dynamic_app(adapter) as (client, domain, body):
        accepted = submit(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "completed_degraded", state
        assert state["budget"]["model_calls"] == 3 and state["budget"]["tool_actions"] == 1
        first = json.loads(adapter.requests[0]["messages"][1]["content"])
        assert not first["observations"]
        assert all("body" not in item for item in first["source_catalog"]["items"])
        second = json.loads(adapter.requests[1]["messages"][1]["content"])
        assert second["observations"][0]["origin"] == "snapshot_tool"
        assert "call_id" not in second["observations"][0]
        with domain.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_child_tasks"
                ).scalar_one()
                == 0
            )
            calls = [
                json.loads(row[0])
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            ]
            assert sum(item.get("kind") == "tool" for item in calls) == 1


@pytest.mark.parametrize("disposition", ["adopted", "partial", "rejected"])
def test_one_level_child_result_is_reviewed_and_billed_to_parent(
    dynamic_app, controlled_adapter, disposition
):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate", disposition=disposition)
    with dynamic_app(adapter) as (client, domain, body):
        accepted = submit(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "completed_degraded", state
        assert state["budget"]["model_calls"] == 5 and state["budget"]["tool_actions"] == 1
        report = client.get(URL + "/" + accepted["review_id"] + "/report").json()
        assert report["payload"]["adopted_child_result_refs"][0]["disposition"] == disposition
        child_requests = [
            json.loads(item["messages"][1]["content"])
            for item in adapter.requests
            if "capability_id" in json.loads(item["messages"][1]["content"])
        ]
        assert len(child_requests) == 2
        assert [item["path"] for item in child_requests[0]["source_catalog"]["items"]] == [
            "docs/api.md"
        ]
        with domain.store.read() as conn:
            child = domain.store.row(conn, "SELECT * FROM contract_review_child_tasks")
            child_body = json.loads(child["body"])
            assert child_body["model_calls"] == 2 and child_body["tool_actions"] == 1
            assert json.loads(child["latest_review"])["disposition"] == disposition
            assert child_body["result"]["evidence_refs"]
            assert len(child_body["evidence_trace"]["observations"]) == 1


@pytest.mark.parametrize(
    ("mode", "expected", "tools"),
    [
        ("invalid_tool", "ACTION_PROTOCOL_ERROR", 2),
        ("missing_review", "ACTION_PROTOCOL_ERROR", 1),
        ("repeat", "NO_PROGRESS", 4),
    ],
)
def test_invalid_actions_and_no_progress_stop_without_unbounded_dispatch(
    dynamic_app, controlled_adapter, mode, expected, tools
):
    adapter = ScriptedAdapter(controlled_adapter(), mode)
    with dynamic_app(adapter) as (client, domain, body):
        accepted = submit(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "failed", state
        assert state["error_code"] == expected
        assert state["budget"]["tool_actions"] == tools
        with domain.store.read() as conn:
            raw = [
                json.loads(row[0])
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            ]
            physical_tools = sum(item.get("kind") == "tool" for item in raw)
            assert physical_tools == (
                0 if mode == "invalid_tool" else 1 if mode == "missing_review" else 3
            )
            if mode == "missing_review":
                assert (
                    domain.store.row(conn, "SELECT latest_review FROM contract_review_child_tasks")[
                        "latest_review"
                    ]
                    is None
                )


def test_child_cannot_delegate_and_parent_sees_failure(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "nested")
    with dynamic_app(adapter) as (client, domain, body):
        accepted = submit(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "completed_degraded", state
        with domain.store.read() as conn:
            rows = conn.exec_driver_sql("SELECT status,body FROM contract_review_child_tasks").all()
            assert len(rows) == 1
            assert json.loads(rows[0].body)["result"]["status"] == "failed"


def test_provider_retry_is_one_physical_retry_in_same_step(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter())
    adapter.failure_once = ProviderFailure(
        "PROVIDER_RATE_LIMITED", retryable=True, remote_outcome="known"
    )
    with dynamic_app(adapter) as (client, domain, body):
        accepted = submit(client, body)
        state = terminal(client, accepted["review_id"])
        assert state["status"] == "completed_degraded", state
        assert state["budget"]["model_calls"] == 4
        assert state["budget"]["usage_status"] == "partial"
        with domain.store.read() as conn:
            rows = conn.exec_driver_sql(
                "SELECT step_id,physical_retry_no FROM contract_review_calls ORDER BY rowid"
            ).all()
            assert rows[0].step_id == rows[1].step_id
            assert [rows[0].physical_retry_no, rows[1].physical_retry_no] == [0, 1]


@pytest.mark.parametrize(
    ("patch", "expected"),
    [({"model_call_limit": 2}, "BUDGET_EXHAUSTED"), ({"tool_action_limit": 1}, "BUDGET_EXHAUSTED")],
)
def test_frozen_parent_budget_cannot_be_bypassed(dynamic_app, controlled_adapter, patch, expected):
    adapter = ScriptedAdapter(
        controlled_adapter(), "repeat" if "tool_action_limit" in patch else "direct"
    )
    with dynamic_app(adapter, patch=patch) as (client, _, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "failed" and state["error_code"] == expected


def test_parent_review_commits_before_subsequent_io(dynamic_app, controlled_adapter, monkeypatch):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    original_complete = adapter.complete

    def with_extra_read(payload):
        result = original_complete(payload)
        data = json.loads(payload["messages"][1]["content"])
        if (
            data.get("child_results")
            and not data.get("child_result_reviews")
            and "candidate_report" not in data
        ):
            report_action = json.loads(result["content"])
            action = read_action(data, "examples/client.py")
            action["child_result_reviews"] = report_action["child_result_reviews"]
            result["content"] = json.dumps(action, ensure_ascii=False)
        return result

    adapter.complete = with_extra_read
    with dynamic_app(adapter) as (client, domain, body):
        original_execute = SnapshotTools.execute
        observed = []

        def inspect_before_io(tools, name, arguments):
            if (
                name == "read_source"
                and tools.sources[arguments["source_id"]]["path"] == "examples/client.py"
            ):
                with domain.store.read() as conn:
                    child = domain.store.row(
                        conn, "SELECT latest_review FROM contract_review_child_tasks"
                    )
                    assert json.loads(child["latest_review"])["disposition"] == "adopted"
                observed.append(True)
            return original_execute(tools, name, arguments)

        monkeypatch.setattr(SnapshotTools, "execute", inspect_before_io)
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "completed_degraded", state
        assert observed == [True]


@pytest.mark.parametrize("fault", ["invalid_action", "storage"])
def test_parent_review_is_not_saved_when_the_whole_action_fails(
    dynamic_app, controlled_adapter, monkeypatch, fault
):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")

    def turn_into_read(action, data):
        if (
            data.get("child_results")
            and not data.get("child_result_reviews")
            and "candidate_report" not in data
        ):
            reviews = action["child_result_reviews"]
            action.clear()
            action.update(read_action(data, "examples/client.py"), child_result_reviews=reviews)
            if fault == "invalid_action":
                action["arguments"]["command"] = "forbidden"

    mutate_adapter(adapter, turn_into_read)
    with dynamic_app(adapter) as (client, domain, body):
        if fault == "storage":
            original = domain.store.event

            def fail(conn, review, input_id, job, kind, payload, **links):
                if kind == "child_result_reviewed":
                    raise ReviewError(
                        "STORAGE_CAPACITY_EXCEEDED", "controlled storage failure", 503
                    )
                return original(conn, review, input_id, job, kind, payload, **links)

            monkeypatch.setattr(domain.store, "event", fail)
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "failed", state
        assert state["error_code"] == (
            "ACTION_PROTOCOL_ERROR" if fault == "invalid_action" else "STORAGE_CAPACITY_EXCEEDED"
        )
        with domain.store.read() as conn:
            assert (
                domain.store.row(conn, "SELECT latest_review FROM contract_review_child_tasks")[
                    "latest_review"
                ]
                is None
            )
            calls = [
                json.loads(row[0])
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            ]
            assert sum(item.get("kind") == "tool" for item in calls) == 1
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_events WHERE event_type='child_resu"
                    "lt_reviewed'"
                ).scalar_one()
                == 0
            )


def test_report_child_summary_must_match_latest_parent_decision(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")

    def mismatch(action, data):
        if data.get("child_results") and action.get("action") == "submit_report":
            action["report"]["adopted_child_result_refs"][0]["disposition"] = "rejected"

    mutate_adapter(adapter, mismatch)
    with dynamic_app(adapter) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["error_code"] == "ACTION_PROTOCOL_ERROR"
        with domain.store.read() as conn:
            assert (
                domain.store.row(conn, "SELECT latest_review FROM contract_review_child_tasks")[
                    "latest_review"
                ]
                is None
            )


@pytest.mark.parametrize(
    "forbidden", ["another_source", "rule_source", "unregistered_capability_tool"]
)
def test_child_actual_requests_and_tools_stay_inside_grants(
    dynamic_app, controlled_adapter, forbidden
):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    parent_catalog = {}

    def malicious(action, data):
        if "capability_id" not in data and "candidate_report" not in data:
            parent_catalog.update(
                {item["path"]: item["source_id"] for item in data["source_catalog"]["items"]}
            )
        if "capability_id" in data:
            action.clear()
            action.update(read_action(data, "docs/api.md", child=True))
            if forbidden == "another_source":
                action["arguments"]["source_id"] = parent_catalog["src/api.py"]
            elif forbidden == "rule_source":
                action["arguments"]["source_id"] = data["adoption_records"][0]["body_ref"][
                    "source_id"
                ]
            else:
                action.update(
                    tool="inspect_json_contract",
                    arguments={"source_id": data["source_catalog"]["items"][0]["source_id"]},
                )

    mutate_adapter(adapter, malicious)
    with dynamic_app(adapter) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "completed_degraded", state
        with domain.store.read() as conn:
            child = json.loads(
                domain.store.row(conn, "SELECT body FROM contract_review_child_tasks")["body"]
            )
            assert child["result"]["status"] == "failed" and child["tool_actions"] == 2
            assert all(
                json.loads(row[0]).get("kind") != "tool"
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            )
        for payload in adapter.requests:
            data = json.loads(payload["messages"][1]["content"])
            if "capability_id" in data:
                assert parent_catalog["src/api.py"] not in payload["messages"][1]["content"]


@pytest.mark.parametrize("quota", ["child_model_limit", "child_tool_limit"])
def test_child_quota_is_not_a_separate_parent_budget(dynamic_app, controlled_adapter, quota):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    if quota == "child_tool_limit":

        def repeat_child(action, data):
            if "capability_id" in data:
                action.clear()
                action.update(read_action(data, "docs/api.md", child=True))

        mutate_adapter(adapter, repeat_child)
    with dynamic_app(adapter, patch={quota: 1}) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "completed_degraded", state
        with domain.store.read() as conn:
            child = json.loads(
                domain.store.row(conn, "SELECT body FROM contract_review_child_tasks")["body"]
            )
            assert child["result"]["status"] == "failed"
            assert child["model_calls" if quota == "child_model_limit" else "tool_actions"] == 1
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_calls WHERE status='dispatch_started'"
                ).scalar_one()
                == 0
            )
            model_calls = sum(
                json.loads(row[0]).get("kind") == "model"
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            )
            assert state["budget"]["model_calls"] == model_calls


def test_no_more_than_two_sequential_children_can_be_accepted(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    initial_delegate = {}

    def delegate_again(action, data):
        if action.get("action") == "delegate_task" and "capability_id" not in data:
            initial_delegate.update(copy.deepcopy(action))
        elif data.get("child_results") and "candidate_report" not in data:
            reviews = [
                {
                    "child_result_ref": item["child_result_ref"],
                    "disposition": "rejected",
                    "reason": "只保留诊断。",
                }
                for item in data["child_results"]
            ]
            action.clear()
            action.update(copy.deepcopy(initial_delegate), child_result_reviews=reviews)

    mutate_adapter(adapter, delegate_again)
    with dynamic_app(adapter) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["error_code"] == "ACTION_PROTOCOL_ERROR"
        with domain.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_child_tasks"
                ).scalar_one()
                == 2
            )
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_child_tasks WHERE status='running'"
                ).scalar_one()
                == 0
            )


def test_child_timeout_blocks_queue_and_late_body_is_not_accepted(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    adapter.pause = threading.Event()
    with dynamic_app(adapter, patch={"model_timeout_seconds": 0.1}) as (client, domain, body):
        first = submit(client, body)
        assert adapter.entered.wait(3)
        failed = terminal(client, first["review_id"])
        assert failed["error_code"] == "CALL_RESULT_UNKNOWN"
        blocker = failed["dispatch_gate"]["blocked_by"][0]
        second = submit(client, body, "second")
        assert client.get(URL + "/" + second["review_id"]).json()["status"] == "queued"
        assert len(adapter.requests) == 2
        adapter.pause.set()
        assert terminal(client, second["review_id"])["status"] == "completed_degraded"
        with domain.store.read() as conn:
            old_call = json.loads(
                domain.store.row(
                    conn,
                    "SELECT body FROM contract_review_calls WHERE id=:id",
                    id=blocker["call_id"],
                )["body"]
            )
            assert old_call["result"] is None and old_call["acceptance"] is None
            assert old_call["local_io_state"] == "quiesced"
            old_child = domain.store.row(
                conn,
                "SELECT status,latest_review FROM contract_review_child_tasks WHERE job_id=:job",
                job=first["job_id"],
            )
            assert old_child["status"] == "failed" and old_child["latest_review"] is None


@pytest.mark.parametrize("bad", [None, "wrong_type", "forged_source", "forged_text"])
def test_missing_or_malformed_tool_result_never_becomes_empty_success(
    dynamic_app, controlled_adapter, monkeypatch, bad
):
    adapter = ScriptedAdapter(controlled_adapter())
    original = SnapshotTools.execute

    def corrupt(tools, name, arguments):
        if bad is None:
            return None
        value = original(tools, name, arguments)
        if bad == "wrong_type":
            value["source_refs"] = "not a list"
        elif bad == "forged_source":
            value["source_refs"][0]["source_id"] = "other-input"
        else:
            value["body"]["text"] = "fabricated content"
        return value

    monkeypatch.setattr(SnapshotTools, "execute", corrupt)
    with dynamic_app(adapter) as (client, _, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "failed" and state["error_code"] == "TOOL_RESULT_INVALID"
        assert not state["report_available"]


@pytest.mark.parametrize(
    ("code", "retryable", "calls"),
    [("PROVIDER_AUTH_FAILURE", False, 1), ("PROVIDER_RATE_LIMITED", True, 2)],
)
def test_dependency_retry_stops_at_frozen_limit(
    dynamic_app, controlled_adapter, code, retryable, calls
):
    adapter = ScriptedAdapter(controlled_adapter())
    adapter.failure_once = ProviderFailure(code, retryable=retryable, remote_outcome="known")
    original = adapter.complete

    def always_fail(payload):
        adapter.failed_once = False
        return original(payload)

    adapter.complete = always_fail
    with dynamic_app(adapter) as (client, _, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["error_code"] == code
        assert state["budget"]["model_calls"] == calls == len(adapter.requests)


def test_http_adapter_wire_payload_equals_durable_projection(dynamic_app, controlled_adapter):
    actor = ScriptedAdapter(controlled_adapter())
    wire = []

    def handle(request):
        payload = json.loads(request.content)
        wire.append(payload)
        response = actor.complete(payload)
        return httpx.Response(
            200,
            json={
                "model": "controlled-test",
                "choices": [{"message": {"content": response["content"]}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        )

    adapter = OpenAIReviewAdapter(
        OpenAICompatibleConfig(
            "https://offline.invalid/v1", "synthetic-wire-key", "controlled-test", 5
        ),
        transport=httpx.MockTransport(handle),
        execution_mode="test",
    )
    with dynamic_app(adapter) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "completed_degraded", state
        with domain.store.read() as conn:
            records = [
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT body FROM contract_review_calls ORDER BY rowid"
                )
            ]
            model_records = [
                json.loads(item) for item in records if json.loads(item).get("kind") == "model"
            ]
            assert [item["projection"]["payload"] for item in model_records] == wire
            assert all("synthetic-wire-key" not in item for item in records)


def test_storage_recovery_settles_original_call_then_resumes_queue(
    dynamic_app, controlled_adapter, monkeypatch
):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    adapter.pause = threading.Event()
    available = threading.Event()
    available.set()
    with dynamic_app(adapter) as (client, domain, body):
        original = domain.store.event

        def storage(conn, review, input_id, job, kind, payload, **links):
            if not available.is_set() and kind in ("call_quiesced", "usage_settled", "job_failed"):
                raise ReviewError("DEPENDENCY_UNAVAILABLE", "controlled unavailable storage", 503)
            return original(conn, review, input_id, job, kind, payload, **links)

        monkeypatch.setattr(domain.store, "event", storage)
        try:
            first = submit(client, body)
            assert adapter.entered.wait(3)
            second = submit(client, body, "second")
            available.clear()
            adapter.pause.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not domain.worker.faulted:
                time.sleep(0.01)
            assert domain.worker.faulted
            state = client.get(URL + "/" + first["review_id"]).json()
            assert not state["dispatch_gate"]["can_claim"]
            assert state["evidence_integrity"] == "incomplete"
            assert len(adapter.requests) == 2
            assert client.get(URL + "/" + second["review_id"]).json()["status"] == "queued"
            available.set()
            domain.worker.wake_event.set()
            assert (
                terminal(client, first["review_id"])["error_code"] == "EVIDENCE_PERSISTENCE_FAILED"
            )
            assert terminal(client, second["review_id"])["status"] == "completed_degraded"
        finally:
            available.set()
            adapter.pause.set()


def test_unexpected_host_failure_does_not_leave_a_running_job(
    dynamic_app, controlled_adapter, monkeypatch
):
    adapter = ScriptedAdapter(controlled_adapter())
    recorded, release = threading.Event(), threading.Event()
    original = DynamicLedger.fail

    def fail(*args, **kwargs):
        raise RuntimeError("controlled host failure")

    def record_then_pause(ledger, context, code, elapsed=None):
        original(ledger, context, code, elapsed)
        recorded.set()
        assert release.wait(5)

    monkeypatch.setattr(RunState, "build", fail)
    monkeypatch.setattr(DynamicLedger, "fail", record_then_pause)
    with dynamic_app(adapter) as (client, domain, body):
        try:
            accepted = submit(client, body)
            assert recorded.wait(3)
            state = terminal(client, accepted["review_id"])
            assert state["status"] == "failed" and state["error_code"] == "INTERNAL_ERROR"
            assert domain.worker.faulted and not adapter.requests
            assert not state["dispatch_gate"]["can_claim"]
            queued = submit(client, body, "after-host-failure")
            release.set()
            domain.worker.thread.join(3)
            assert not domain.worker.thread.is_alive()
            assert client.get(URL + "/" + queued["review_id"]).json()["status"] == "queued"
            assert not adapter.requests
        finally:
            release.set()


def test_output_usage_overrun_is_recorded_without_truncation_and_stops_dispatch(
    dynamic_app, controlled_adapter
):
    adapter = ScriptedAdapter(controlled_adapter())
    original = adapter.complete

    def overrun(payload):
        result = original(payload)
        result["usage"]["output_tokens"] = 8001
        return result

    adapter.complete = overrun
    with dynamic_app(adapter) as (client, _, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["error_code"] == "BUDGET_EXHAUSTED"
        assert state["budget"]["output_tokens"] == 8001
        assert state["budget"]["model_calls"] == len(adapter.requests) == 1


def test_sufficient_context_can_submit_without_tool_or_delegation(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "submit")
    with dynamic_app(adapter, delegation=False) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "completed_degraded", state
        assert state["budget"]["model_calls"] == len(adapter.requests) == 2
        assert state["budget"]["tool_actions"] == 0
        with domain.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_child_tasks"
                ).scalar_one()
                == 0
            )
            assert [
                json.loads(row[0])["kind"]
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            ] == ["model", "model"]


def test_disabled_delegation_rejects_action_without_child_dispatch(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    with dynamic_app(adapter, delegation=False) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["error_code"] == "ACTION_PROTOCOL_ERROR", state
        assert len(adapter.requests) == 2
        assert all(
            "capability_id" not in json.loads(payload["messages"][1]["content"])
            for payload in adapter.requests
        )
        with domain.store.read() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM contract_review_child_tasks"
                ).scalar_one()
                == 0
            )


def test_expired_child_scope_returns_failure_and_parent_can_continue(
    dynamic_app, controlled_adapter, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    original = DynamicLedger.start_child

    def expired(ledger, context, call_id, action):
        identifier, reference, _ = original(ledger, context, call_id, action)
        deadline = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        with ledger.store.transaction() as conn:
            row = ledger.store.row(
                conn, "SELECT body FROM contract_review_child_tasks WHERE id=:id", id=identifier
            )
            value = json.loads(row["body"])
            value["deadline"] = deadline
            ledger.store.execute(
                conn,
                "UPDATE contract_review_child_tasks SET body=:body WHERE id=:id",
                id=identifier,
                body=json.dumps(value),
            )
        return identifier, reference, deadline

    monkeypatch.setattr(DynamicLedger, "start_child", expired)
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    with dynamic_app(adapter) as (client, domain, body):
        state = terminal(client, submit(client, body)["review_id"])
        assert state["status"] == "completed_degraded", state
        assert len(adapter.requests) == 3  # Parent delegate, parent report, fixed review.
        with domain.store.read() as conn:
            child = json.loads(
                domain.store.row(conn, "SELECT body FROM contract_review_child_tasks")["body"]
            )
            assert child["result"]["status"] == "failed"
            assert child["result"]["limitations"] == ["CHILD_DEADLINE_EXCEEDED"]
            assert child["model_calls"] == child["tool_actions"] == 0


def test_inflight_child_uses_its_deadline_before_model_timeout(dynamic_app, controlled_adapter):
    adapter = ScriptedAdapter(controlled_adapter(), "delegate")
    adapter.pause = threading.Event()
    with dynamic_app(adapter, patch={"child_seconds": 0.2, "model_timeout_seconds": 5}) as (
        client,
        domain,
        body,
    ):
        accepted = submit(client, body)
        assert adapter.entered.wait(3)
        started = time.monotonic()
        state = terminal(client, accepted["review_id"])
        assert state["error_code"] == "CALL_RESULT_UNKNOWN", state
        assert time.monotonic() - started < 3
        assert len(adapter.requests) == 2
        assert not state["dispatch_gate"]["can_claim"]
        adapter.pause.set()
