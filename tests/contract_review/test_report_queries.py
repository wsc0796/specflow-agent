"""Read projections preserve authoritative reports and distinguish missing evidence."""

import copy
import json
import re
import threading

import pytest
from test_checkpoints import HumanAdapter, answer, batch, footprint, frozen, post, terminal, waiting
from test_verification_import import completed_review as completed_review
from test_verification_import import next_input

from specflow.contract_review import reporting
from specflow.contract_review import service as service_module
from specflow.contract_review.common import canonical
from specflow.contract_review.reporting import render_report
from specflow.db import Project

URL = "/api/v1/contract-reviews"


def submit(client, body, key="review"):
    response = client.post(URL, json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()


def test_json_stays_authoritative_markdown_has_checks_quality_and_locator(completed_review):
    client, domain, review_id, _, report = completed_review
    before = footprint(domain, review_id)
    markdown = client.get(f"{URL}/{review_id}/report", params={"format": "markdown"})
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    for value in (
        "# 契约审查报告",
        "逐检查项",
        "冻结行为",
        "quality",
        "NOT_RUN",
        "处理任务",
        "验收项",
        "证据定位",
        report["job_id"],
        report["report_revision_id"],
    ):
        assert value in markdown.text
    assert report["check_manifest"][0]["behavior"] in markdown.text
    assert client.get(f"{URL}/{review_id}/report").json() == report
    assert client.get(f"{URL}/{review_id}/report", params={"format": "json"}).json() == report
    assert footprint(domain, review_id) == before


def test_renderer_preserves_long_tail_escapes_markup_and_fences(completed_review):
    _, domain, review_id, _, original = completed_review
    report = copy.deepcopy(original)
    report["payload"]["summary"] = "<script>alert(1)</script>\n# injected [click](javascript:bad)"
    report["payload"]["findings"][0]["claim"] = "完整长文本" * 150 + "不可截断尾部"
    report["rules"][0]["body"] = "```\n<script>bad</script>\n![image](https://invalid)"
    report["rules"][0]["provenance"] = {"text": "```\n# break fence"}
    value = frozen(domain, review_id, report["input_revision_id"])
    text = render_report(report, value)
    assert "不可截断尾部" in text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "\n# injected" not in text
    assert "[click](javascript:bad)" not in text
    assert "````json" in text
    assert report["payload"]["summary"] != original["payload"]["summary"]
    assert domain.report(review_id) == original


def test_readable_work_and_acceptance_keep_dependencies_scope_and_not_run(
    running_app, controlled_adapter
):
    with running_app(HumanAdapter(controlled_adapter(), later_work="ready")) as (client, _, body):
        review_id, state, report = waiting(client, body)
        response = post(client, review_id, batch(state, report, [answer(), answer("q_material")]))
        assert response.status_code == 202
        assert terminal(client, review_id)["status"] == "completed_degraded"
        markdown = client.get(f"{URL}/{review_id}/report", params={"format": "markdown"}).text
        for value in (
            "取得获准证据",
            "depends_on",
            "proposed_scope",
            "execution_authorized",
            "false",
            "NOT_RUN",
            "required_environment",
            "取得证据",
            "静态审查",
        ):
            assert value in markdown
        assert '"execution_status": "PASS"' not in markdown


@pytest.mark.parametrize("format", ["json", "markdown"])
def test_current_failure_does_not_fall_back_to_historical_report(completed_review, format):
    client, domain, review_id, _, report = completed_review
    next_input(domain, review_id, selected=[])
    result = client.get(f"{URL}/{review_id}/report", params={"format": format})
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "REPORT_NOT_AVAILABLE"
    old = client.get(
        f"{URL}/{review_id}/report",
        params={"format": format, "report_revision_id": report["report_revision_id"]},
    )
    assert old.status_code == 200
    if format == "json":
        assert old.json() == report
    else:
        assert report["input_revision_id"] in old.text
    assert (
        client.get(f"{URL}/{review_id}/questions").json()["error"]["code"] == "REPORT_NOT_AVAILABLE"
    )


def test_render_failure_preserves_json_and_authoritative_state(completed_review, monkeypatch):
    client, domain, review_id, _, report = completed_review
    before = footprint(domain, review_id)

    def fail(*args):
        raise OSError("controlled export failure")

    monkeypatch.setattr(reporting, "render_report", fail)
    failed = client.get(f"{URL}/{review_id}/report", params={"format": "markdown"})
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "controlled export failure" not in failed.text
    assert client.get(f"{URL}/{review_id}/report").json() == report
    assert footprint(domain, review_id) == before


def test_questions_show_partial_answers_and_explicit_historical_ownership(
    running_app, controlled_adapter
):
    with running_app(HumanAdapter(controlled_adapter())) as (client, domain, body):
        review_id, state, report = waiting(client, body)
        path = f"{URL}/{review_id}/questions"
        initial = client.get(path).json()
        assert initial["is_current_report"]
        assert all(
            q["answer_status"] == "unanswered" and q["resolution"] is None for q in initial["items"]
        )
        partial = post(client, review_id, batch(state, report))
        assert partial.status_code == 200
        current = client.get(path).json()
        assert current["remaining_blocking_question_ids"] == ["q_material"]
        assert current["items"][0]["resolution"]["answer"]["scope"] == "this_review"
        old_state = client.get(f"{URL}/{review_id}").json()
        last = post(client, review_id, batch(old_state, report, [answer("q_material")]), "last")
        assert last.status_code == 202
        terminal(client, review_id)
        before = footprint(domain, review_id)
        historical = client.get(
            path, params={"report_revision_id": report["report_revision_id"]}
        ).json()
        assert not historical["is_current_report"]
        assert historical["input_revision_id"] == report["input_revision_id"]
        assert historical["remaining_blocking_question_ids"] == []
        assert {q["answer_status"] for q in historical["items"]} == {"answered"}
        assert client.get(path).json()["items"] == []
        assert (
            client.get(
                f"{URL}/other/questions",
                params={"report_revision_id": report["report_revision_id"]},
            ).status_code
            == 404
        )
        assert footprint(domain, review_id) == before


def test_review_list_keyset_uses_created_at_id_and_binds_project(review_client, monkeypatch):
    client, domain, body = review_client
    original = service_module.identity
    identifiers = iter(("cr_z", "cr_a"))
    monkeypatch.setattr(
        service_module,
        "identity",
        lambda prefix: next(identifiers) if prefix == "cr" else original(prefix),
    )
    monkeypatch.setattr(service_module, "now", lambda: "2026-11-01T00:00:00Z")
    submit(client, body, "z")
    submit(client, body, "a")
    query = {"project_id": body["project_id"], "limit": 1}
    first = client.get(URL, params=query).json()
    assert [x["review_id"] for x in first["items"]] == ["cr_a"]
    second = client.get(URL, params={**query, "cursor": first["next_cursor"]}).json()
    assert [x["review_id"] for x in second["items"]] == ["cr_z"]
    assert second["next_cursor"] is None
    with domain.store.database.factory() as session:
        root = session.get(Project, body["project_id"]).repository_path
        session.add(Project(id="other", name="Other", repository_path=root + "-other"))
        session.commit()
    assert (
        client.get(
            URL, params={**query, "project_id": "other", "cursor": first["next_cursor"]}
        ).status_code
        == 422
    )
    assert client.get(URL, params={"project_id": "other"}).json()["items"] == []
    assert client.get(URL, params={"project_id": "missing"}).status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        "project_id=project-test&limit=0",
        "project_id=project-test&limit=101",
        "project_id=project-test&cursor=broken",
        "project_id=project-test&cursor=",
        "project_id=project-test&limit=1&limit=2",
        "project_id=project-test&unknown=x",
    ],
)
def test_query_bounds_and_unknown_duplicates_are_rejected(review_client, query):
    client, _, _ = review_client
    assert client.get(URL + "?" + query).status_code == 422


def test_new_query_and_format_routes_are_authenticated(completed_review):
    client, _, review_id, _, _ = completed_review
    auth = client.headers.pop("X-API-Key")
    try:
        for path in (
            URL + "?project_id=project-test",
            f"{URL}/{review_id}/questions",
            f"{URL}/{review_id}/report?format=markdown",
        ):
            assert client.get(path).status_code == 401
    finally:
        client.headers["X-API-Key"] = auth
    for query in ("format=html", "format=markdown&format=json", "format=markdown&unknown=x"):
        assert client.get(f"{URL}/{review_id}/report?" + query).status_code == 422


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("body", "payload_unavailable"),
        ("hash", "payload_integrity_mismatch"),
        ("ref", "payload_reference_mismatch"),
        ("large", "payload_too_large"),
        ("metadata", "event_metadata_unavailable"),
        ("job-missing", "event_metadata_unavailable"),
        ("input-foreign", "event_metadata_unavailable"),
        ("type-foreign", "event_metadata_unavailable"),
    ],
)
def test_event_payload_gaps_are_explicit_and_do_not_modify_records(review_client, fault, reason):
    client, domain, body = review_client
    accepted = submit(client, body)
    path = f"{URL}/{accepted['review_id']}/events"
    event = client.get(path).json()["items"][0]
    with domain.store.transaction() as conn:
        if fault in ("job-missing", "input-foreign", "type-foreign"):
            changed = dict(event)
            if fault == "job-missing":
                changed.pop("job_id")
            else:
                changed["input_revision_id" if fault == "input-foreign" else "event_type"] = (
                    "foreign"
                )
            domain.store.execute(
                conn,
                "UPDATE contract_review_events SET body=:body WHERE id=:id",
                body=canonical(changed),
                id=event["event_id"],
            )
        elif fault == "metadata":
            domain.store.execute(
                conn,
                "UPDATE contract_review_events SET body='{}' WHERE id=:id",
                id=event["event_id"],
            )
        elif fault == "ref":
            changed = {**event, "payload_ref": "foreign-event"}
            domain.store.execute(
                conn,
                "UPDATE contract_review_events SET body=:body WHERE id=:id",
                body=canonical(changed),
                id=event["event_id"],
            )
        else:
            value = "{" if fault == "body" else "x" * (1024**2 + 1) if fault == "large" else "{}"
            domain.store.execute(
                conn,
                "UPDATE contract_review_events SET payload=:payload WHERE id=:id",
                payload=value,
                id=event["event_id"],
            )
    before = footprint(domain, accepted["review_id"])
    metadata = client.get(path).json()["items"][0]
    assert metadata["payload_available"] is False
    assert metadata["evidence_integrity"] == "incomplete"
    assert metadata["missing_evidence"] == [reason]
    detail = client.get(path + "/" + event["event_id"])
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "EVENT_PAYLOAD_NOT_AVAILABLE"
    assert footprint(domain, accepted["review_id"]) == before


def test_event_pagination_job_filter_and_projection_body_are_linked(completed_review):
    client, _, review_id, _, report = completed_review
    path = f"{URL}/{review_id}/events"
    query = {"limit": 2, "job_id": report["job_id"]}
    items, cursor = [], None
    while True:
        page = client.get(path, params={**query, **({"cursor": cursor} if cursor else {})}).json()
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    seq = [item["event_seq"] for item in items]
    assert seq == sorted(set(seq))
    projections = []
    for item in items:
        assert item["job_id"] == report["job_id"]
        detail = client.get(path + "/" + item["event_id"]).json()
        assert detail["payload_available"]
        if "material_entries" in detail["payload"]:
            projections.append(detail["payload"])
    assert projections and all(p["payload"]["messages"][1]["content"] for p in projections)
    first = client.get(path, params=query).json()
    assert client.get(path, params={"cursor": first["next_cursor"]}).status_code == 422
    assert client.get(f"{URL}/missing/events/{items[0]['event_id']}").status_code == 404
    assert client.get(path, params={"job_id": "foreign"}).status_code == 404


def test_status_projects_real_step_deadline_unknown_and_dispatch_gate(
    running_app, controlled_adapter
):
    pause = threading.Event()
    adapter = controlled_adapter(pauses={1: pause})
    with running_app(adapter, timeout=5.0) as (client, _, body):
        accepted = submit(client, body)
        assert adapter.entered[1].wait(3)
        state = client.get(f"{URL}/{accepted['review_id']}").json()
        assert state["current_step"]["role"] == "analysis"
        assert state["deadline"] and state["started_at"] and state["finished_at"] is None
        assert state["last_call"]["remote_outcome"] == "unknown"
        assert state["last_call"]["usage"]["input_tokens"] is None
        assert state["dispatch_gate"]["can_claim"] is False
        assert state["dispatch_gate"]["blocked_by"][0]["call_id"] == state["last_call"]["call_id"]
        pause.set()
        final = terminal(client, accepted["review_id"])
        assert final["finished_at"]
        assert final["last_call"]["remote_outcome"] == "known"


def test_markdown_keeps_host_accepted_coverage_source_slice(running_app, controlled_adapter):
    class CoverageAdapter(controlled_adapter):
        def complete(self, payload):
            result = super().complete(payload)
            data = json.loads(payload["messages"][1]["content"])
            if "candidate_report" not in data:
                action = json.loads(result["content"])
                action["report"]["coverage"][0]["source_refs"] = [
                    {
                        "source_id": data["sources"][0]["source_id"],
                        "selector": {"kind": "lines", "start_line": 1, "end_line": 1},
                    }
                ]
                result["content"] = json.dumps(action, ensure_ascii=False)
            return result

    with running_app(CoverageAdapter()) as (client, _, body):
        accepted = submit(client, body)
        assert terminal(client, accepted["review_id"])["status"] == "completed_degraded"
        path = f"{URL}/{accepted['review_id']}/report"
        coverage = client.get(path).json()["payload"]["coverage"]
        markdown = client.get(path, params={"format": "markdown"}).text
        assert "逐目标覆盖的来源片段" in markdown
        projected = [
            json.loads(value) for value in re.findall(r"```json\n(.*?)\n```", markdown, re.DOTALL)
        ]
        expected = [
            {"target_id": item["target_id"], "source_refs": item["source_refs"]}
            for item in coverage
        ]
        assert expected in projected
