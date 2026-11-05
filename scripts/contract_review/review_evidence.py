"""Read existing review APIs; keep each input/job/report and explicit evidence gaps."""

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path


class PreparationError(ValueError):
    """A bounded preparation/workflow refusal, without credentials or response headers."""


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise PreparationError("INVALID_RESOURCE_ID")
    return value


class ReviewEvidence:
    def __init__(self, client, *, max_pages=100):
        if type(max_pages) is not int or not 1 <= max_pages <= 1000:
            raise PreparationError("INVALID_PAGE_LIMIT")
        self.client, self.max_pages = client, max_pages
        self.data = {
            "schema_version": "cr02-b1-evidence.v1",
            "semantic_verdict": "NOT_RUN",
            "collection_complete": True,
            "states": [],
            "inputs": {},
            "jobs": {},
            "reports": {},
            "questions": {},
            "events": {},
            "request_projections": {},
            "target_adoptions": {},
            "ruleset_views": {},
            "mutations": [],
            "gaps": [],
            "api_reads": [],
        }

    def gap(self, code, **context):
        item = {"code": code, **context}
        if item not in self.data["gaps"]:
            self.data["gaps"].append(item)
        self.data["collection_complete"] = False

    def read(self, path, *, params=None, plain=False):
        try:
            response = self.client.get(path, params=params or {})
            self.data["api_reads"].append(
                {
                    "path": path,
                    "params": copy.deepcopy(params or {}),
                    "status": response.status_code,
                }
            )
            if response.status_code != 200:
                self.gap("READ_FAILED", path=path, status=response.status_code)
                return None
            body = response.text if plain else response.json()
            if not plain and not isinstance(body, dict):
                raise ValueError("Expected object")
            return body
        except Exception as error:
            self.gap("READ_ERROR", path=path, error_type=type(error).__name__)
            return None

    def pages(self, path, *, params=None):
        cursor, seen, items = None, set(), []
        for _ in range(self.max_pages):
            query = {**(params or {}), "limit": 20}
            if cursor:
                query["cursor"] = cursor
            page = self.read(path, params=query)
            if page is None:
                return items, False
            if not isinstance(page.get("items"), list) or "next_cursor" not in page:
                self.gap("INVALID_PAGE", path=path)
                return items, False
            if (
                params
                and "ruleset_version" in params
                and page.get("ruleset_version") != params["ruleset_version"]
            ):
                self.gap("RULESET_VERSION_MISMATCH", path=path)
                return items, False
            items.extend(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                return items, True
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                self.gap("INVALID_OR_REPEATED_CURSOR", path=path)
                return items, False
            seen.add(cursor)
        self.gap("PAGE_LIMIT", path=path)
        return items, False

    def ruleset(self, project_id, version):
        identifier(project_id)
        if type(version) is not int or version < 0:
            raise PreparationError("INVALID_RULESET_VERSION")
        path = f"/api/v1/projects/{project_id}/contract-decisions"
        items, complete = self.pages(path, params={"ruleset_version": version})
        record = {"ruleset_version": version, "items": items, "complete": complete}
        key = f"{project_id}:{version}"
        old = self.data["ruleset_views"].get(key)
        if old is not None and old != record:
            self.gap("HISTORICAL_RULESET_CHANGED", project_id=project_id, version=version)
        else:
            self.data["ruleset_views"][key] = copy.deepcopy(record)
        return record

    def job(self, review_id, job_id):
        identifier(review_id)
        identifier(job_id)
        base = f"/api/v1/contract-reviews/{review_id}"
        gap_count = len(self.data["gaps"])
        events, complete = self.pages(base + "/events", params={"job_id": job_id})
        ids = set()
        for metadata in events:
            if not isinstance(metadata, dict):
                self.gap("INVALID_EVENT", job_id=job_id)
                continue
            event_id = metadata.get("event_id")
            if (
                metadata.get("review_id") != review_id
                or metadata.get("job_id") != job_id
                or not isinstance(event_id, str)
                or event_id in ids
            ):
                self.gap("EVENT_IDENTITY_MISMATCH", job_id=job_id)
                continue
            ids.add(event_id)
            try:
                identifier(event_id)
            except PreparationError:
                self.gap("INVALID_EVENT_ID", job_id=job_id)
                continue
            if metadata.get("payload_available") is not True:
                self.gap("EVENT_PAYLOAD_UNAVAILABLE", event_id=event_id)
                continue
            detail = self.read(base + "/events/" + event_id)
            if detail is None:
                continue
            if (
                any(
                    detail.get(k) != metadata.get(k)
                    for k in ("event_id", "review_id", "job_id", "input_revision_id", "event_type")
                )
                or "payload" not in detail
            ):
                self.gap("EVENT_DETAIL_MISMATCH", event_id=event_id)
                continue
            old = self.data["events"].get(event_id)
            if old is not None and old != detail:
                self.gap("EVENT_CHANGED", event_id=event_id)
                continue
            self.data["events"][event_id] = copy.deepcopy(detail)
            if detail["event_type"] == "request_projected":
                projection = detail["payload"]
                wire = projection.get("payload") if isinstance(projection, dict) else None
                if (
                    not isinstance(wire, dict)
                    or not isinstance(wire.get("messages"), list)
                    or not wire["messages"]
                ):
                    self.gap("REQUEST_BODY_MISSING", event_id=event_id)
                else:
                    self.data["request_projections"][event_id] = copy.deepcopy(projection)
        self.data["jobs"].setdefault(job_id, {"review_id": review_id})
        self.data["jobs"][job_id]["events_complete"] = (
            self.data["jobs"][job_id].get("events_complete", True)
            and complete
            and len(self.data["gaps"]) == gap_count
        )

    def report(self, review_id, report_id):
        identifier(report_id)
        base = f"/api/v1/contract-reviews/{review_id}/report"
        body = self.read(base, params={"report_revision_id": report_id})
        markdown = self.read(
            base, params={"report_revision_id": report_id, "format": "markdown"}, plain=True
        )
        if body is None or markdown is None:
            return None
        if body.get("review_id") != review_id or body.get("report_revision_id") != report_id:
            self.gap("REPORT_IDENTITY_MISMATCH", report_id=report_id)
            return None
        record = {"json": body, "markdown": markdown}
        old = self.data["reports"].get(report_id)
        if old is not None and old != record:
            self.gap("HISTORICAL_REPORT_CHANGED", report_id=report_id)
            return None
        self.data["reports"].setdefault(report_id, copy.deepcopy(record))
        self.data["target_adoptions"][report_id] = copy.deepcopy(body.get("rules", []))
        return body

    def capture(self, review_id):
        identifier(review_id)
        base = f"/api/v1/contract-reviews/{review_id}"
        state = self.read(base)
        if state is None:
            return None
        if state.get("review_id") != review_id:
            self.gap("STATE_IDENTITY_MISMATCH", review_id=review_id)
            return None
        try:
            input_id = identifier(state["current_input_revision_id"])
            job_id = identifier(state["job_id"])
        except (PreparationError, KeyError):
            self.gap("STATE_INPUT_OR_JOB_MISSING", review_id=review_id)
            return None
        snapshot = copy.deepcopy(state)
        if state.get("evidence_integrity") == "incomplete":
            self.gap("HOST_EVIDENCE_INCOMPLETE", review_id=review_id)
        self.data["states"].append(snapshot)
        frozen_identity = {
            k: snapshot.get(k)
            for k in ("input_hash", "execution_profile", "adopted_ruleset_version")
        }
        old = self.data["inputs"].get(input_id)
        if old is not None and old["frozen_identity"] != frozen_identity:
            self.gap("FROZEN_INPUT_IDENTITY_CHANGED", input_id=input_id)
        elif old is None:
            self.data["inputs"][input_id] = {
                "review_id": review_id,
                "frozen_identity": frozen_identity,
                "first_state": copy.deepcopy(snapshot),
            }
        owner = self.data["jobs"].setdefault(job_id, {"review_id": review_id, "input_id": input_id})
        if owner["review_id"] != review_id or owner.get("input_id", input_id) != input_id:
            self.gap("JOB_IDENTITY_MISMATCH", job_id=job_id)
        for known_job, record in list(self.data["jobs"].items()):
            if record["review_id"] == review_id:
                self.job(review_id, known_job)
        for known_report, record in list(self.data["reports"].items()):
            if record["json"]["review_id"] == review_id:
                self.report(review_id, known_report)
        report_id = state.get("current_report_revision_id")
        if state.get("report_available") and report_id:
            body = self.report(review_id, report_id)
            if not any(
                event.get("job_id") == job_id and event.get("event_type") == "request_projected"
                for event in self.data["events"].values()
            ):
                self.gap("REQUEST_PROJECTION_MISSING", job_id=job_id)
                self.data["jobs"][job_id]["events_complete"] = False
            questions = self.read(base + "/questions", params={"report_revision_id": report_id})
            if body is not None and body.get("input_revision_id") != input_id:
                self.gap("REPORT_INPUT_MISMATCH", report_id=report_id)
            if questions is not None:
                if (
                    questions.get("input_revision_id") != input_id
                    or questions.get("report_revision_id") != report_id
                ):
                    self.gap("QUESTION_IDENTITY_MISMATCH", report_id=report_id)
                else:
                    self.data["questions"][report_id] = copy.deepcopy(questions)
        elif state["status"] in ("completed", "completed_degraded", "awaiting_decision"):
            self.gap("FORMAL_REPORT_MISSING", job_id=job_id)
        self.data["workflow_status"] = state["status"]
        return snapshot

    def wait(self, review_id, *, seconds=10.0, interval=0.01):
        if not 0 < seconds <= 60 or not 0 < interval <= 1:
            raise PreparationError("INVALID_WAIT_BOUND")
        base = f"/api/v1/contract-reviews/{identifier(review_id)}"
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = self.read(base)
            if state is None or state.get("status") not in ("queued", "running"):
                return self.capture(review_id)
            time.sleep(interval)
        self.gap("OBSERVATION_TIMEOUT", review_id=review_id)
        return self.capture(review_id)

    def save(self, output):
        output = Path(output).resolve()
        repository = Path(__file__).resolve().parents[2]
        if output.is_relative_to(repository):
            raise PreparationError("OUTPUT_MUST_BE_OUTSIDE_CHECKOUT")
        output.mkdir(parents=True, exist_ok=False)
        path = output / "review-evidence.json"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(self.data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        return path
