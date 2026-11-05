"""Collector contracts: preserve bodies and history, distinguish scope and missing evidence."""

import copy

import httpx
import pytest
from test_public_case_prep import evidence_module

ReviewEvidence = evidence_module.ReviewEvidence


class EvidenceAPI:
    def __init__(self):
        self.calls = []
        self.fault = None
        self.state = {
            "review_id": "cr_demo",
            "project_id": "project_demo",
            "version": 2,
            "current_input_revision_id": "input_1",
            "input_hash": "hash-1",
            "job_id": "job_1",
            "current_report_revision_id": "report_1",
            "status": "completed_degraded",
            "report_available": True,
            "execution_profile": {"execution_mode": "test", "profile_id": "controlled"},
            "adopted_ruleset_version": 1,
            "current_ruleset_version": 1,
            "budget": {"model_calls": 2, "usage_status": "unknown"},
        }
        self.reports = {"report_1": self.make_report("report_1", "input_1", "job_1")}

    @staticmethod
    def make_report(report, input_id, job):
        return {
            "review_id": "cr_demo",
            "report_revision_id": report,
            "input_revision_id": input_id,
            "job_id": job,
            "rules": [
                {
                    "adoption_id": "adopt_1",
                    "target_id": "target_1",
                    "body": "正式规则全文",
                    "disposition": "adopted",
                    "reason_code": "EXACT_SCOPE_MATCH",
                }
            ],
            "payload": {"questions": []},
        }

    def handle(self, request):
        path, query = request.url.path, dict(request.url.params)
        self.calls.append((path, query))
        base = "/api/v1/contract-reviews/cr_demo"
        if path == base:
            return httpx.Response(200, json=self.state)
        if path.endswith("/contract-decisions"):
            rule = {
                "project_decision_id": "decision_1",
                "operation": "confirm",
                "text": "正式规则全文",
                "effective_scope_expression": {
                    "base_scope": {"api_versions": ["v2"]},
                    "removal_slices": [],
                },
                "removal_relations": [],
                "effect_relations": [],
            }
            return httpx.Response(
                200,
                json={
                    "ruleset_version": 2 if self.fault == "wrong_version" else 1,
                    "items": [rule],
                    "next_cursor": None,
                },
            )
        if path == base + "/events":
            if self.fault == "empty_events":
                return httpx.Response(200, json={"items": [], "next_cursor": None})
            job = query["job_id"]
            start = 20 if query.get("cursor") else 0
            count = 21 if job == "job_1" else 1
            items = [self.metadata(job, n) for n in range(start, min(start + 20, count))]
            cursor = "page-two" if start == 0 and count > 20 else None
            if self.fault == "cursor":
                cursor = "page-two"
            if self.fault == "cursor_type":
                cursor = {"untrusted": True}
            if self.fault == "payload" and items:
                items[0]["payload_available"] = False
            if self.fault == "owner" and items:
                items[0]["job_id"] = "foreign_job"
            return httpx.Response(200, json={"items": items, "next_cursor": cursor})
        if path.startswith(base + "/events/"):
            event = path.rsplit("/", 1)[1]
            job, number = event.rsplit("_event_", 1)
            if self.fault == "detail":
                return httpx.Response(404, json={})
            metadata = self.metadata(job, int(number))
            payload = {
                "role": "analysis",
                "input_hash": "hash-1" if job == "job_1" else "hash-2",
                "payload": {"messages": [{"role": "user", "content": "完整请求正文"}]},
                "material_entries": [{"body": "完整规则正文"}],
            }
            if self.fault == "request_body":
                payload["payload"] = "body unavailable"
            return httpx.Response(200, json={**metadata, "payload": payload})
        if path == base + "/report":
            report = query.get("report_revision_id")
            if self.fault == "report" or report not in self.reports:
                return httpx.Response(404, json={})
            if query.get("format") == "markdown":
                return httpx.Response(200, text="报告原文 " + report)
            return httpx.Response(200, json=self.reports[report])
        if path == base + "/questions":
            return httpx.Response(
                200,
                json={
                    "review_id": "cr_demo",
                    "input_revision_id": self.state["current_input_revision_id"],
                    "report_revision_id": query["report_revision_id"],
                    "items": [],
                },
            )
        return httpx.Response(404, json={})

    @staticmethod
    def metadata(job, n):
        return {
            "event_id": job + "_event_" + str(n),
            "review_id": "cr_demo",
            "job_id": job,
            "input_revision_id": "input_1" if job == "job_1" else "input_2",
            "event_type": "request_projected",
            "payload_available": True,
        }

    def client(self):
        return httpx.Client(
            base_url="http://testserver", transport=httpx.MockTransport(self.handle)
        )


def test_rule_views_and_target_adoptions_use_separate_sources():
    api = EvidenceAPI()
    with api.client() as client:
        collector = ReviewEvidence(client)
        view = collector.ruleset("project_demo", 1)
        collector.capture("cr_demo")
    assert "disposition" not in view["items"][0]
    assert "removal_slices" in view["items"][0]["effective_scope_expression"]
    adopted = collector.data["target_adoptions"]["report_1"][0]
    assert adopted["disposition"] == "adopted"
    assert adopted["reason_code"] == "EXACT_SCOPE_MATCH"
    assert adopted["body"] == "正式规则全文"
    assert collector.data["collection_complete"]


def test_all_event_pages_and_each_successor_job_are_collected():
    api = EvidenceAPI()
    with api.client() as client:
        collector = ReviewEvidence(client)
        collector.capture("cr_demo")
        api.state.update(
            current_input_revision_id="input_2",
            input_hash="hash-2",
            job_id="job_2",
            current_report_revision_id="report_2",
            version=4,
        )
        api.reports["report_2"] = api.make_report("report_2", "input_2", "job_2")
        collector.capture("cr_demo")
    assert len(collector.data["events"]) == len(collector.data["request_projections"]) == 22
    assert set(collector.data["jobs"]) == {"job_1", "job_2"}
    assert any(q.get("cursor") == "page-two" for _, q in api.calls)
    assert collector.data["collection_complete"], collector.data["gaps"]


@pytest.mark.parametrize(
    "fault",
    [
        "payload",
        "detail",
        "report",
        "cursor",
        "cursor_type",
        "owner",
        "empty_events",
        "request_body",
    ],
)
def test_missing_payload_history_report_or_cursor_marks_incomplete(fault):
    api = EvidenceAPI()
    api.fault = fault
    with api.client() as client:
        collector = ReviewEvidence(client, max_pages=3)
        collector.capture("cr_demo")
    assert collector.data["collection_complete"] is False
    assert collector.data["gaps"]
    assert len(api.calls) < 80
    assert collector.data["semantic_verdict"] == "NOT_RUN"
    if fault in ("payload", "detail", "owner"):
        assert collector.data["jobs"]["job_1"]["events_complete"] is False


def test_historical_input_evidence_uses_saved_snapshots_without_input_api(tmp_path):
    api = EvidenceAPI()
    with api.client() as client:
        collector = ReviewEvidence(client)
        first = collector.capture("cr_demo")
        retained = copy.deepcopy(collector.data["inputs"]["input_1"])
        api.state.update(
            current_input_revision_id="input_2",
            input_hash="hash-2",
            job_id="job_2",
            current_report_revision_id="report_2",
            version=4,
        )
        api.reports["report_2"] = api.make_report("report_2", "input_2", "job_2")
        collector.capture("cr_demo")
        collector.save(tmp_path / "saved")
    assert collector.data["inputs"]["input_1"] == retained
    assert retained["first_state"] == first
    assert set(collector.data["reports"]) == {"report_1", "report_2"}
    assert all("/inputs" not in p and "input_revision_id" not in q for p, q in api.calls)


@pytest.mark.parametrize("status", ["failed", "interrupted", "queued"])
def test_unknown_or_failed_job_is_not_semantic_pass(status):
    api = EvidenceAPI()
    api.state.update(
        status=status,
        report_available=False,
        current_report_revision_id=None,
        error_code="CALL_RESULT_UNKNOWN",
    )
    with api.client() as client:
        collector = ReviewEvidence(client)
        collector.wait("cr_demo", seconds=0.02, interval=0.001)
    assert collector.data["workflow_status"] == status
    assert collector.data["semantic_verdict"] == "NOT_RUN"
    assert collector.data["states"][-1]["budget"]["usage_status"] == "unknown"
    if status == "queued":
        assert any(g["code"] == "OBSERVATION_TIMEOUT" for g in collector.data["gaps"])


def test_changed_history_and_wrong_ruleset_version_are_explicit_gaps():
    api = EvidenceAPI()
    with api.client() as client:
        collector = ReviewEvidence(client)
        collector.capture("cr_demo")
        api.reports["report_1"]["payload"]["questions"] = [{"id": "changed"}]
        collector.capture("cr_demo")
        assert any(g["code"] == "HISTORICAL_REPORT_CHANGED" for g in collector.data["gaps"])
        api.fault = "wrong_version"
        other = ReviewEvidence(client)
        other.ruleset("project_demo", 1)
        assert not other.data["collection_complete"]
