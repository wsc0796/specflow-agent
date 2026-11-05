"""Read explicit archives; diagnose a historical job without executing its contents."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from review_evidence import identifier

from specflow.contract_review.common import canonical, digest
from specflow.contract_review.sources import strict_json

B2_ORDER_SOURCE = "73e33e182ad304c77dd8a3ea35eff3949798d5fe85c7d9336e71aea4765f286d"
SCHEMA = "cr02-diagnosis-ab.v1"


class DiagnosisError(ValueError):
    def __init__(self, code, exit_code=2, candidates=()):
        super().__init__(code)
        self.code, self.exit_code, self.candidates = code, exit_code, list(candidates)


def resource(value):
    try:
        return identifier(value)
    except ValueError:
        raise DiagnosisError("INVALID_RESOURCE_ID") from None


def require(value, code="INVALID_ARCHIVE_SHAPE", exit_code=3):
    if not value:
        raise DiagnosisError(code, exit_code)


def pointer(*parts):
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def reference(source, path, **identity):
    return {"source": source, "pointer": path, **identity}


def aggregate(values):
    values = list(values)
    if "FAIL" in values:
        return "FAIL"
    if not values or "UNDETERMINED" in values:
        return "UNDETERMINED"
    if all(v == "NOT_APPLICABLE" for v in values):
        return "NOT_APPLICABLE"
    return "PASS"


def result(verdict, refs=(), **fields):
    return {"verdict": verdict, "evidence_refs": list(refs), **fields}


def read_bytes(path, limit):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit, "INPUT_SIZE_LIMIT")
        return raw
    except OSError:
        raise DiagnosisError("INPUT_IO_ERROR", 3) from None


def parse(raw):
    try:
        return strict_json(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        raise DiagnosisError("INVALID_JSON", 3) from None


def payload_data(payload):
    """Business JSON is a string inside the complete wire object."""
    try:
        value = strict_json(payload["messages"][1]["content"])
        return value if isinstance(value, dict) else None
    except (ValueError, KeyError, IndexError, TypeError, RecursionError):
        return None


def text_locations(value, text, path=""):
    if not text:
        return []
    if isinstance(value, str):
        return [path] if text in value else []
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in text_locations(v, text, path + pointer(k))]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in text_locations(v, text, path + pointer(i))]
    return []


def wire_locations(wire, text):
    # Parse embedded JSON for field locations, but do not ignore other messages/fields.
    locations = []
    for key, value in wire.items():
        if key != "messages":
            locations.extend(text_locations(value, text, pointer(key)))
    for i, message in enumerate(wire.get("messages", [])):
        value = message
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            try:
                value = {**message, "content": strict_json(message["content"])}
            except ValueError:
                pass
        locations.extend(text_locations(value, text, pointer("messages", i)))
    return locations


def safe_fields(value):
    """Only categorical state, resource IDs and usage; prose stays in the archive."""
    if not isinstance(value, dict):
        return {}
    names = {
        "code",
        "error_code",
        "status",
        "job_status",
        "local_io_state",
        "remote_outcome",
        "outcome",
        "disposition",
        "accepted",
        "kind",
        "role",
        "execution_instance_id",
        "child_result_ref",
        "report_revision_id",
        "resolution_id",
        "next_job_id",
        "input_revision_id",
        "reason_code",
        "retryable",
        "stage",
        "judgment_status",
        "execution_status",
        "verification_mode",
        "execution_mode",
        "adoption_id",
        "target_id",
        "project_decision_id",
        "call_id",
        "failed",
    }
    out = {}
    for key in names & value.keys():
        item = value[key]
        if item is None or type(item) is bool:
            out[key] = item
        elif isinstance(item, str):
            try:
                out[key] = identifier(item)
            except ValueError:
                pass
    for key in ("usage", "usage_reserved"):
        if isinstance(value.get(key), dict):
            out[key] = {
                k: v
                for k, v in value[key].items()
                if k in {"input_tokens", "output_tokens"} and (v is None or type(v) is int)
            }
    for key in ("acceptance", "evidence", "last_call", "result"):
        if isinstance(value.get(key), dict):
            out[key] = safe_fields(value[key])
    return out


def safe_assessments(values):
    items = []
    for value in values:
        item = {}
        for field in ("id", "verdict", "controlled_fixture"):
            candidate = value.get(field)
            if isinstance(candidate, str) and len(candidate) <= 128:
                if all(c.isascii() and (c.isalnum() or c in "_.-") for c in candidate):
                    item[field] = candidate
        if type(value.get("physical_model_calls")) is int:
            item["physical_model_calls"] = value["physical_model_calls"]
        items.append(item)
    return items


class Archive:
    def __init__(self, data, *, source="evidence", ledger=(), order_source=None):
        require(isinstance(data, dict))
        self.data, self.source = data, source
        self.ledger, self.order_source = list(ledger), order_source
        self.gaps, self.findings, self.invalid_events = [], [], set()
        self.jobs, self.reports, self.events = {}, {}, {}
        self.calls, self.unbound_calls = [], []
        self.event_refs = {}
        self._index()

    def ref(self, *parts, **identity):
        return reference(self.source, pointer(*parts), **identity)

    def gap(self, code, refs=(), state="MISSING"):
        item = {"code": code, "evidence_state": state, "evidence_refs": list(refs)}
        if item not in self.gaps:
            self.gaps.append(item)

    def finding(self, code, verdict, refs=(), **fields):
        self.findings.append({"code": code, **result(verdict, refs, **fields)})

    def owner(self, review, job, input_id):
        values = tuple(resource(x) for x in (review, job, input_id))
        prior = self.jobs.get(job)
        require(prior is None or prior == values, "JOB_OWNERSHIP_CONFLICT", 2)
        self.jobs[job] = values
        known = self.data.get("inputs", {}).get(input_id)
        if known is not None:
            require(known.get("review_id") == review, "INPUT_OWNERSHIP_CONFLICT", 2)
        return values

    def _index(self):
        for field in ("jobs", "reports", "inputs", "test_store_inputs", "request_projections"):
            require(isinstance(self.data.get(field, {}), dict))
        for field in ("states", "test_store_calls", "test_store_resolutions", "mutations"):
            require(isinstance(self.data.get(field, []), list))
        for job, item in self.data.get("jobs", {}).items():
            self.owner(item["review_id"], job, item["input_id"])
        for key, wrapper in self.data.get("reports", {}).items():
            report = wrapper["json"]
            require(key == report["report_revision_id"], "REPORT_KEY_MISMATCH", 2)
            resource(key)
            self.owner(report["review_id"], report["job_id"], report["input_revision_id"])
            self.reports[key] = report
        raw = self.data.get("events")
        require(isinstance(raw, (dict, list)))
        self.kind = "b2" if isinstance(raw, dict) else "f01"
        pairs = raw.items() if isinstance(raw, dict) else enumerate(raw)
        sequences = set()
        for key, event in pairs:
            require(isinstance(event, dict))
            eid = resource(event["event_id"])
            require(eid not in self.events, "DUPLICATE_EVENT_ID", 2)
            require(not isinstance(raw, dict) or eid == key, "EVENT_KEY_MISMATCH", 2)
            resource(event["review_id"])
            resource(event["input_revision_id"])
            resource(event["event_type"])
            if event.get("job_id") is not None:
                self.owner(event["review_id"], event["job_id"], event["input_revision_id"])
            seq = event["event_seq"]
            require(type(seq) is int and seq > 0)
            require((event["review_id"], seq) not in sequences, "EVENT_SEQUENCE_CONFLICT", 2)
            sequences.add((event["review_id"], seq))
            for field in ("call_id", "logical_call_id", "caused_by_event_id"):
                if event.get(field) is not None:
                    resource(event[field])
            self.events[eid] = event
            self.event_refs[eid] = self.ref("events", key, event_id=eid)
        for state in self.states:
            if state.get("job_id") and state.get("current_input_revision_id"):
                self.owner(state["review_id"], state["job_id"], state["current_input_revision_id"])
        call_ids = set()
        for index, original in enumerate(self.data.get("test_store_calls", [])):
            call = {**original, "archive_index": index}
            if "call_id" not in call or "job_id" not in call:
                # The historical UNKNOWN control exported only the stored body.
                # Bind by an existing unique projection identity, never by array position.
                projection = call.get("projection", {})
                candidates = [
                    e
                    for e in self.events.values()
                    if e["event_type"] == "request_projected"
                    and e["review_id"] == call.get("review_id")
                    and e["input_revision_id"] == call.get("input_id")
                    and projection.get("projection_id")
                    and e.get("payload") == projection
                ]
                if len(candidates) != 1:
                    self.unbound_calls.append(call)
                    continue
                call.update(
                    call_id=candidates[0]["call_id"],
                    job_id=candidates[0]["job_id"],
                    identity_method="unique_projection_identity",
                )
            cid = resource(call["call_id"])
            require(cid not in call_ids, "DUPLICATE_CALL_ID", 2)
            call_ids.add(cid)
            self.owner(call["review_id"], call["job_id"], call["input_id"])
            self.calls.append(call)
        for iid, frozen in self.data.get("test_store_inputs", {}).items():
            require(iid == frozen["input_revision_id"], "FROZEN_INPUT_ID_MISMATCH", 2)
        for event in self.events.values():
            cause = self.events.get(event.get("caused_by_event_id"))
            if cause:
                require(cause["review_id"] == event["review_id"], "FOREIGN_EVENT_REFERENCE", 2)
            if event["event_type"] == "report_committed":
                rid = (event.get("payload") or {}).get("report_revision_id")
                report = self.reports.get(rid)
                if report:
                    require(
                        (report["review_id"], report["job_id"], report["input_revision_id"])
                        == (event["review_id"], event["job_id"], event["input_revision_id"]),
                        "REPORT_EVENT_OWNERSHIP_CONFLICT",
                        2,
                    )

    @property
    def states(self):
        return self.data.get("states", []) + (
            [self.data["status"]] if isinstance(self.data.get("status"), dict) else []
        )

    def state(self, job):
        states = [s for s in self.states if s.get("job_id") == job]
        if states:
            return states[-1]
        failed = [
            e
            for e in self.events.values()
            if e.get("job_id") == job and e["event_type"] == "job_failed"
        ]
        return {"job_status": "failed", **failed[-1].get("payload", {})} if failed else {}

    def select(self, *, report_id=None, review_id=None, job_id=None, failure=True):
        for value in (report_id, review_id, job_id):
            if value is not None:
                resource(value)
        if report_id:
            report = self.reports.get(report_id)
            require(report is not None, "REPORT_NOT_FOUND", 2)
            require(review_id in (None, report["review_id"]), "REPORT_REVIEW_MISMATCH", 2)
            require(job_id in (None, report["job_id"]), "REPORT_JOB_MISMATCH", 2)
            review_id, job_id = report["review_id"], report["job_id"]
        else:
            require(review_id is not None, "REVIEW_REQUIRED", 2)
            if job_id is None:
                candidates = [
                    j
                    for j, owner in self.jobs.items()
                    if owner[0] == review_id and self.state(j).get("job_status") == "failed"
                ]
                if (
                    self.data.get("collection_complete") is not True
                    or self.data.get("gaps")
                    or self.data.get("evidence_status") == "INCOMPLETE"
                    or any(
                        j.get("events_complete") is False
                        for j in self.data.get("jobs", {}).values()
                        if j.get("review_id") == review_id
                    )
                    or len(candidates) != 1
                ):
                    raise DiagnosisError("FAILED_JOB_SELECTION_REQUIRED", candidates=candidates)
                job_id = candidates[0]
            require(job_id in self.jobs, "JOB_NOT_FOUND", 2)
            require(self.jobs[job_id][0] == review_id, "JOB_REVIEW_MISMATCH", 2)
            if failure:
                require(self.state(job_id).get("job_status") == "failed", "JOB_NOT_FAILED", 2)
        owner = self.jobs[job_id]
        return {
            "review_id": owner[0],
            "job_id": owner[1],
            "input_revision_id": owner[2],
            "report_revision_id": report_id,
        }

    def scoped(self, subject):
        return sorted(
            (e for e in self.events.values() if e.get("job_id") == subject["job_id"]),
            key=lambda e: e["event_seq"],
        )

    def verify_event(self, event):
        ref = self.event_refs[event["event_id"]]
        payload = event.get("payload")
        state = "PRESENT"
        if (
            not isinstance(payload, dict)
            or event.get("payload_available") is False
            or event.get("missing_evidence")
            or event.get("evidence_integrity") == "incomplete"
        ):
            self.gap("EVENT_PAYLOAD_MISSING", [ref])
            state = "MISSING"
        elif event.get("payload_hash") and digest(payload) != event["payload_hash"]:
            self.gap("EVENT_PAYLOAD_HASH_CONFLICT", [ref], "CONFLICTING")
            state = "CONFLICTING"
        elif event["event_type"] == "request_projected":
            cached = self.data.get("request_projections", {}).get(event["event_id"])
            if (
                payload.get("projection_hash")
                and digest(payload.get("payload")) != payload["projection_hash"]
            ) or (cached is not None and cached != payload):
                self.gap("PROJECTION_CONFLICT", [ref], "CONFLICTING")
                state = "CONFLICTING"
            wire = payload.get("payload")
            valid_wire = isinstance(wire, dict)
            if payload.get("role") == "tool":
                valid_wire = (
                    valid_wire
                    and isinstance(wire.get("tool"), str)
                    and isinstance(wire.get("arguments"), dict)
                )
            else:
                valid_wire = valid_wire and payload_data(wire) is not None
            if not valid_wire:
                self.gap("PROJECTED_REQUEST_BODY_INVALID", [ref])
                state = "MISSING"
        if state != "PRESENT":
            self.invalid_events.add(event["event_id"])
        cause = event.get("caused_by_event_id")
        if cause and cause not in self.events:
            self.gap("CAUSAL_EVENT_MISSING", [ref])
        return state

    def projections(self, events):
        return [
            e
            for e in events
            if e["event_type"] == "request_projected"
            and (e.get("payload") or {}).get("role") != "tool"
        ]

    def pair(self):
        models = self.projections(self.events.values())
        pairs = {
            e["call_id"]: result(
                "UNDETERMINED",
                [self.event_refs[e["event_id"]]],
                boundary="adapter" if self.kind == "b2" else "transport",
                method="unavailable",
                evidence_state="NOT_CAPTURED",
            )
            for e in models
        }
        duplicate_calls = {
            e["call_id"] for e in models if sum(x["call_id"] == e["call_id"] for x in models) != 1
        }
        if duplicate_calls:
            self.gap("AMBIGUOUS_PHYSICAL_CALL")
            return pairs, {}
        received = {}
        if self.kind == "b2":
            calls = [c for c in self.calls if c["kind"] == "model"]
            wires = self.data.get("adapter_delivery")
            if self.order_source != B2_ORDER_SOURCE:
                self.gap("ADAPTER_ORDER_PROVENANCE_UNKNOWN", state="NOT_CAPTURED")
                return pairs, received
            if not isinstance(wires, list) or not len(calls) == len(wires) == len(models):
                self.gap("ADAPTER_PAIR_COVERAGE_INCOMPLETE")
                return pairs, received
            by_call = {e["call_id"]: e for e in models}
            if set(by_call) != {c["call_id"] for c in calls}:
                self.gap("ADAPTER_PAIR_CALL_SET_MISMATCH")
                return pairs, received
            for i, (call, wire) in enumerate(zip(calls, wires, strict=True)):
                cid = call["call_id"]
                event = by_call[cid]
                require(
                    (event["review_id"], event["job_id"], event["input_revision_id"])
                    == (call["review_id"], call["job_id"], call["input_id"]),
                    "CALL_OWNERSHIP_CONFLICT",
                    2,
                )
                refs = [self.event_refs[event["event_id"]], self.ref("adapter_delivery", i)]
                if event["event_id"] in self.invalid_events:
                    pairs[cid] = result(
                        "UNDETERMINED",
                        refs,
                        boundary="adapter",
                        method="b2_store_rowid_v1",
                        evidence_state="CONFLICTING",
                    )
                    continue
                equal = canonical(event["payload"]["payload"]) == canonical(wire)
                equal &= canonical(call["projection"]["payload"]) == canonical(wire)
                if call["projection"].get("projection_hash") != digest(
                    call["projection"]["payload"]
                ):
                    self.gap("STORE_PROJECTION_HASH_CONFLICT", refs, "CONFLICTING")
                    pairs[cid] = result(
                        "UNDETERMINED",
                        refs,
                        boundary="adapter",
                        method="b2_store_rowid_v1",
                        evidence_state="CONFLICTING",
                    )
                    continue
                pairs[cid] = result(
                    "PASS" if equal else "FAIL",
                    refs,
                    boundary="adapter",
                    method="b2_store_rowid_v1",
                    evidence_state="PRESENT",
                )
                received[cid] = wire
        else:
            reserved = [
                (i, row)
                for i, row in enumerate(self.ledger)
                if row.get("event") == "reserved_before_adapter_http"
            ]
            for event in models:
                cid = event["call_id"]
                if event["event_id"] in self.invalid_events:
                    continue
                payload = event["payload"]["payload"]
                matches = [
                    (i, r) for i, r in reserved if canonical(r.get("payload")) == canonical(payload)
                ]
                if len(matches) != 1:
                    self.gap("TRANSPORT_PAIR_NOT_UNIQUE", [self.event_refs[event["event_id"]]])
                    continue
                i, reservation = matches[0]
                trial_id = resource(reservation["trial_call_id"])
                starts = [
                    (j, r)
                    for j, r in enumerate(self.ledger)
                    if r.get("event") == "http_transport_entered"
                    and r.get("trial_call_id") == trial_id
                ]
                reverse = sum(
                    canonical((e.get("payload") or {}).get("payload")) == canonical(payload)
                    for e in models
                )
                refs = [
                    self.event_refs[event["event_id"]],
                    reference("trial_ledger", f"/lines/{i + 1}", trial_call_id=trial_id),
                ]
                valid = (
                    len(starts) == 1
                    and starts[0][0] > i
                    and reverse == 1
                    and sum(r.get("trial_call_id") == trial_id for _, r in reserved) == 1
                    and reservation.get("wire_hash") == digest(payload)
                    and len(reserved) == len(models)
                    and self.data.get("collection_complete") is True
                )
                if valid:
                    refs.append(
                        reference(
                            "trial_ledger", f"/lines/{starts[0][0] + 1}", trial_call_id=trial_id
                        )
                    )
                    received[cid] = payload
                else:
                    self.gap("TRANSPORT_PAIR_COVERAGE_OR_HASH", refs)
                pairs[cid] = result(
                    "PASS" if valid else "UNDETERMINED",
                    refs,
                    boundary="transport",
                    method="unique_complete_json",
                    evidence_state="PRESENT" if valid else "MISSING",
                    trial_call_id=trial_id,
                    remote_receipt="unknown",
                )
        return pairs, received

    def frozen(self, subject):
        iid = subject["input_revision_id"]
        value = self.data.get("test_store_inputs", {}).get(iid)
        ref = self.ref("test_store_inputs", iid)
        if value is None:
            self.gap("FROZEN_INPUT_NOT_CAPTURED", [ref], "NOT_CAPTURED")
            return None
        expected = value.get("input_hash")
        binding = (
            self.data.get("inputs", {}).get(iid, {}).get("frozen_identity", {}).get("input_hash")
        )
        if binding is not None and binding != expected:
            self.gap("FROZEN_INPUT_BINDING_CONFLICT", [ref], "CONFLICTING")
            return None
        if (
            not expected
            or digest({k: v for k, v in value.items() if k != "input_hash"}) != expected
        ):
            self.gap("FROZEN_INPUT_HASH_CONFLICT", [ref], "CONFLICTING")
            return None
        return value

    def content(self, subject, events, frozen):
        checks = []
        if self.projections(events) and frozen is not None:
            self.gap(
                "INDEPENDENT_CASE_MATERIALS_NOT_CAPTURED",
                [self.ref("test_store_inputs", subject["input_revision_id"])],
                "NOT_CAPTURED",
            )
        for event in self.projections(events):
            cid, proj = event["call_id"], event.get("payload") or {}
            ref = self.event_refs[event["event_id"]]
            wire = proj.get("payload", {})
            data = payload_data(wire)
            obligations = []

            def obligation(name, verdict, **details):
                obligations.append({"obligation": name, **result(verdict, [ref], **details)})

            if (
                frozen is None
                or data is None
                or event["event_id"] in self.invalid_events
                or proj.get("child_task_id")
            ):
                obligation("frozen_parent_context", "UNDETERMINED")
            else:
                for field in ("adoption_records", "resolutions"):
                    obligation(
                        field,
                        "PASS"
                        if canonical(data.get(field)) == canonical(frozen.get(field))
                        else "FAIL",
                    )
                for rule in frozen.get("adoption_records", []):
                    if rule["disposition"] != "adopted":
                        continue
                    rid = resource(rule["adoption_id"])
                    materials = data.get("rule_materials", [])
                    if rule.get("origin", {}).get("kind") == "project_decision":
                        body = rule.get("body")
                        valid = isinstance(body, str) and digest(body.encode()) == rule["body_hash"]
                        obligation(
                            "frozen_rule_body", "PASS" if valid else "UNDETERMINED", adoption_id=rid
                        )
                        if not valid:
                            continue
                        locations = wire_locations(wire, body)
                        channel = any(
                            m.get("adoption_id") == rid and m.get("body") == body for m in materials
                        )
                        obligation(
                            "rule_material_channel",
                            "PASS" if channel else "FAIL",
                            adoption_id=rid,
                            body_locations=locations,
                        )
                        obligation(
                            "required_body_present",
                            "PASS" if locations else "FAIL",
                            adoption_id=rid,
                            body_locations=locations,
                        )
                    else:
                        matched = [m for m in materials if m.get("source_ref") == rule["body_ref"]]
                        valid = any(
                            isinstance(m.get("body"), str)
                            and digest(m["body"].encode()) == rule["body_hash"]
                            for m in matched
                        )
                        obligation(
                            "authority_fragment",
                            "PASS" if valid else "FAIL",
                            adoption_id=rid,
                            selector=rule["body_ref"]["selector"],
                        )
                if "candidate_report" in data:
                    self.candidate_checks(event, data, events, obligation)
                # Frozen input binds rules/answers, not a full independent source manifest.
                obligation(
                    "all_case_source_materials",
                    "UNDETERMINED",
                    missing="independent_frozen_source_manifest_and_bodies",
                )
            checks.append(
                {
                    "call_id": cid,
                    "role": proj.get("role"),
                    "verdict": aggregate(o["verdict"] for o in obligations),
                    "obligations": obligations,
                }
            )
        return result(
            aggregate(c["verdict"] for c in checks),
            calls=checks,
            scope="frozen_parent_rules_answers_and_candidate_citations",
            inspected_boundary="host_projection",
            full_case_coverage="UNDETERMINED",
        )

    def candidate_checks(self, event, data, events, add):
        candidate = data["candidate_report"]
        previous = [
            e
            for e in events
            if e["event_seq"] < event["event_seq"]
            and e["event_type"] == "action_proposed"
            and e.get("payload", {}).get("action") == "submit_report"
            and e.get("payload", {}).get("report") == candidate
            and e["event_id"] not in self.invalid_events
        ]
        if len(previous) != 1 or data.get("candidate_report_hash") != digest(candidate):
            add("candidate_origin", "UNDETERMINED")
            return
        add("candidate_origin", "PASS", proposal_ref=self.event_refs[previous[0]["event_id"]])
        source_refs, observation_ids = [], set()
        for collection in (
            "coverage",
            "check_results",
            "findings",
            "work_items",
            "acceptance_items",
        ):
            for item in candidate.get(collection, []):
                source_refs.extend(item.get("source_refs", []))
                observation_ids.update(item.get("observation_refs", []))
        for question in candidate.get("questions", []):
            for item in question.get("evidence_refs", []):
                if item.get("kind") == "source":
                    source_refs.append(item["source_ref"])
                elif item.get("kind") == "observation":
                    observation_ids.add(item["observation_id"])
        for source_ref in source_refs:
            material = [
                m for m in data.get("cited_materials", []) if m.get("source_ref") == source_ref
            ]
            add(
                "candidate_cited_source",
                "UNDETERMINED" if material else "FAIL",
                source_id=resource(source_ref["source_id"]),
                missing="independent_source_body" if material else "cited_material_channel",
            )
        for oid in sorted(observation_ids):
            projected = [o for o in data.get("observations", []) if o.get("observation_id") == oid]
            prior = []
            for old in self.projections(events):
                if old["event_seq"] >= event["event_seq"] or old["event_id"] in self.invalid_events:
                    continue
                old_data = payload_data(old["payload"]["payload"]) or {}
                prior.extend(
                    o for o in old_data.get("observations", []) if o.get("observation_id") == oid
                )
            if not projected:
                verdict = "FAIL"
            elif not prior or len({canonical(o) for o in prior}) != 1:
                verdict = "UNDETERMINED"
            else:
                verdict = "PASS" if projected == [prior[0]] else "FAIL"
            add("candidate_observation", verdict, observation_id=resource(oid))

    def isolation(self, subject, compare, pairs, received, frozen):
        if self.data.get("scenario") != "CR02-H03" and compare is None:
            return result("NOT_APPLICABLE", scope="specified_A_resolution_into_B")
        if compare is None:
            return result("UNDETERMINED", missing="explicit_A1_comparison")
        require(compare["review_id"] != subject["review_id"], "ISOLATION_REQUIRES_TWO_REVIEWS", 2)
        af = self.frozen(compare)
        if af is None or not af.get("resolutions"):
            return result("UNDETERMINED", missing="A1_frozen_answer")
        checks = []
        a_events, b_events = (
            self.projections(self.scoped(compare)),
            self.projections(self.scoped(subject)),
        )
        for answer in af["resolutions"]:
            rid = resource(answer["resolution_id"])
            require(answer["review_id"] == compare["review_id"], "ANSWER_REVIEW_MISMATCH", 2)
            report = self.reports.get(answer["report_revision_id"])
            if report:
                require(
                    report["review_id"] == compare["review_id"]
                    and report["input_revision_id"] == answer["input_revision_id"],
                    "ANSWER_ORIGIN_MISMATCH",
                    2,
                )
            stored = [r for r in self.data.get("test_store_resolutions", []) if r["id"] == rid]
            saved = False
            if len(stored) == 1:
                row = stored[0]
                require(
                    row["review_id"] == compare["review_id"]
                    and row["input_id"] == answer["input_revision_id"]
                    and row["report_id"] == answer["report_revision_id"],
                    "SAVED_ANSWER_OWNERSHIP_MISMATCH",
                    2,
                )
                saved = strict_json(row["body"]) == answer
            linked = any(
                m.get("review_id") == compare["review_id"]
                and m.get("response", {}).get("job_id") == compare["job_id"]
                and m.get("response", {}).get("input_revision_id") == compare["input_revision_id"]
                and rid in m.get("response", {}).get("accepted_resolution_ids", [])
                and m.get("status") == 202
                for m in self.data.get("mutations", [])
            )
            linked |= any(
                e["event_type"] == "resolutions_recorded"
                and e["review_id"] == compare["review_id"]
                and e.get("payload", {}).get("next_job_id") == compare["job_id"]
                and rid in canonical(e.get("payload", {}))
                for e in self.events.values()
            )
            needles = (rid, answer["answer"]["text"])
            positive = bool(a_events) and all(
                pairs.get(e["call_id"], {}).get("verdict") == "PASS"
                and all(wire_locations(received.get(e["call_id"], {}), n) for n in needles)
                for e in a_events
            )
            hits = []
            if frozen is not None:
                for n in needles:
                    hits.extend(
                        self.ref(
                            "test_store_inputs",
                            subject["input_revision_id"],
                            field=p,
                            resolution_id=rid,
                        )
                        for p in text_locations(frozen, n)
                    )
            for e in b_events:
                if e["call_id"] in received:
                    for n in needles:
                        hits.extend(
                            {
                                **pairs[e["call_id"]]["evidence_refs"][-1],
                                "field": p,
                                "call_id": e["call_id"],
                                "resolution_id": rid,
                            }
                            for p in wire_locations(received[e["call_id"]], n)
                        )
            complete = (
                saved
                and report is not None
                and linked
                and positive
                and frozen is not None
                and bool(b_events)
                and self.data.get("collection_complete") is True
                and all(pairs.get(e["call_id"], {}).get("verdict") == "PASS" for e in b_events)
                and not self.invalid_events
            )
            verdict = "FAIL" if hits else "PASS" if complete else "UNDETERMINED"
            checks.append(
                result(
                    verdict,
                    hits,
                    resolution_id=rid,
                    saved=saved,
                    origin_report_present=report is not None,
                    derived_job_linked=linked,
                    A_positive_control=positive,
                    B_call_count=len(b_events),
                    origin=self.ref("reports", answer["report_revision_id"], "json"),
                )
            )
        return result(
            aggregate(c["verdict"] for c in checks),
            answers=checks,
            scope="specified_A_resolution_into_B",
        )

    def rejections(self, events):
        for rejected in events:
            if rejected["event_type"] != "action_rejected":
                continue
            self.finding(
                "HOST_ACTION_REJECTED",
                "FAIL",
                [self.event_refs[rejected["event_id"]]],
                host_error=safe_fields(rejected.get("payload", {})),
            )
            proposals = [
                e
                for e in events
                if e.get("call_id") == rejected.get("call_id")
                and e["event_type"] == "action_proposed"
            ]
            projections = [
                e for e in self.projections(events) if e.get("call_id") == rejected.get("call_id")
            ]
            if len(proposals) != 1 or len(projections) != 1:
                continue
            proposal, projection = proposals[0], projections[0]
            if any(e["event_id"] in self.invalid_events for e in (proposal, projection)):
                continue
            data = payload_data(projection["payload"]["payload"]) or {}
            observations = {o["observation_id"] for o in data.get("observations", [])}
            external = {o["evidence_id"] for o in data.get("verification_evidence", [])}
            report = proposal.get("payload", {}).get("report", {})
            for collection, field in (
                ("findings", "verification_evidence_refs"),
                ("acceptance_items", "evidence_refs"),
            ):
                for i, item in enumerate(report.get(collection, [])):
                    wrong = [
                        v for v in item.get(field, []) if v in observations and v not in external
                    ]
                    if wrong:
                        self.finding(
                            "OBSERVATION_IN_EXTERNAL_EVIDENCE_FIELD",
                            "FAIL",
                            [
                                self.event_refs[e["event_id"]]
                                for e in (projection, proposal, rejected)
                            ],
                            field=pointer("payload", "report", collection, i, field),
                            observation_ids=wrong,
                            attribution="reconstructed_structural_fact",
                        )

    def diagnose(self, subject, compare=None):
        events = self.scoped(subject)
        related = self.scoped(compare) if compare else []
        # Pairing needs all model projections, including earlier jobs in the same export.
        relevant = {
            e["event_id"]: e for e in events + related + self.projections(self.events.values())
        }
        states = {eid: self.verify_event(e) for eid, e in relevant.items()}
        if self.data.get("collection_complete") is not True:
            self.gap("SOURCE_COLLECTION_INCOMPLETE", [self.ref("collection_complete")])
        job_record = self.data.get("jobs", {}).get(subject["job_id"], {})
        if job_record.get("events_complete") is False:
            self.gap("JOB_EVENTS_INCOMPLETE", [self.ref("jobs", subject["job_id"])])
        for i, _ in enumerate(self.data.get("gaps", [])):
            self.gap("SOURCE_RECORDED_GAP", [self.ref("gaps", i)])
        for e in events:
            if e["event_type"] == "report_committed":
                rid = (e.get("payload") or {}).get("report_revision_id")
                if rid not in self.reports:
                    self.gap("COMMITTED_REPORT_MISSING", [self.event_refs[e["event_id"]]])
        timeline = []
        for e in events:
            p = e.get("payload") or {}
            timeline.append(
                {
                    "event_id": e["event_id"],
                    "event_seq": e["event_seq"],
                    "event_type": e["event_type"],
                    "call_id": e.get("call_id"),
                    "logical_call_id": e.get("logical_call_id"),
                    "occurred_at": e.get("occurred_at"),
                    "recorded_at": e.get("recorded_at"),
                    "evidence_state": states[e["event_id"]],
                    "state": safe_fields(p),
                    "evidence_refs": [self.event_refs[e["event_id"]]],
                }
            )
            if e["event_type"] == "job_failed" and p.get("error_code") == "BUDGET_EXHAUSTED":
                stage = p.get("stage")
                self.finding(
                    "BUDGET_FAILURE",
                    "FAIL",
                    [self.event_refs[e["event_id"]]],
                    stage=stage
                    if stage in {"context_build", "dispatch", "execution"}
                    else "UNDETERMINED",
                )
                if stage is None:
                    self.gap(
                        "BUDGET_STAGE_NOT_CAPTURED",
                        [self.event_refs[e["event_id"]]],
                        "NOT_CAPTURED",
                    )
        pairs, received = self.pair()
        frozen = self.frozen(subject)
        content = self.content(subject, events, frozen)
        isolation = self.isolation(subject, compare, pairs, received, frozen)
        self.rejections(events)
        model_events = self.projections(events)
        selected_pairs = [{"call_id": e["call_id"], **pairs[e["call_id"]]} for e in model_events]
        boundary = (
            "projection_matches_adapter" if self.kind == "b2" else "projection_matches_transport"
        )
        acceptance = [
            t
            for t in timeline
            if t["event_type"]
            in {
                "action_rejected",
                "result_rejected",
                "result_accepted",
                "child_result_reviewed",
                "report_committed",
                "job_failed",
            }
        ]
        call_states = []
        for call in self.calls:
            if call["job_id"] == subject["job_id"]:
                call_states.append(
                    {
                        "call_id": call["call_id"],
                        "kind": call["kind"],
                        "state": safe_fields(call),
                        "identity_method": call.get("identity_method", "explicit_call_id"),
                        "evidence_refs": [self.ref("test_store_calls", call["archive_index"])],
                    }
                )
        for call in self.unbound_calls:
            if (
                call.get("review_id") == subject["review_id"]
                and call.get("input_id") == subject["input_revision_id"]
            ):
                self.gap(
                    "CALL_SNAPSHOT_IDENTITY_UNDETERMINED",
                    [self.ref("test_store_calls", call["archive_index"])],
                )
                call_states.append(
                    {
                        "call_id": None,
                        "kind": call.get("kind"),
                        "state": safe_fields(call),
                        "identity_method": "unbound",
                        "evidence_refs": [self.ref("test_store_calls", call["archive_index"])],
                    }
                )
        related_evidence = []
        frontier = [e.get("caused_by_event_id") for e in events]
        seen = {e["event_id"] for e in events}
        while frontier:
            eid = frontier.pop()
            if eid is None or eid in seen or eid not in self.events:
                continue
            seen.add(eid)
            previous = self.events[eid]
            self.verify_event(previous)
            related_evidence.append(self.event_refs[eid])
            frontier.append(previous.get("caused_by_event_id"))
        for e in self.events.values():
            if (
                e["event_type"] == "resolutions_recorded"
                and e["review_id"] == subject["review_id"]
                and (e.get("payload") or {}).get("next_job_id") == subject["job_id"]
            ):
                self.verify_event(e)
                related_evidence.append(self.event_refs[e["event_id"]])
        report = self.reports.get(subject["report_revision_id"])
        report_summary = None
        if report is not None:
            if not any(
                e["event_type"] == "report_committed"
                and (e.get("payload") or {}).get("report_revision_id")
                == subject["report_revision_id"]
                for e in events
            ):
                self.gap(
                    "REPORT_COMMIT_EVENT_MISSING",
                    [self.ref("reports", subject["report_revision_id"])],
                )
            report_summary = {
                **safe_fields(report),
                "adopted_ruleset_version": report.get("adopted_ruleset_version"),
                "rules": [
                    {
                        **safe_fields(r),
                        "body_hash": r.get("body_hash"),
                        "origin": safe_fields(r.get("origin", {})),
                    }
                    for r in report.get("rules", [])
                ],
                "findings": [
                    {"finding_id": resource(f["id"]), **safe_fields(f)}
                    for f in report.get("payload", {}).get("findings", [])
                ],
                "evidence_refs": [self.ref("reports", subject["report_revision_id"], "json")],
            }
        return {
            "schema_version": SCHEMA,
            "subject": subject,
            "source_coverage": {
                "source_kind": self.kind,
                "source_collection_complete": self.data.get("collection_complete"),
                "source_evidence_status": self.data.get("evidence_status"),
                "diagnostic_collection_complete": not self.gaps,
                "adapter_order_source_sha256": self.order_source,
                "selected_events": len(events),
                "model_calls": len(model_events),
                "tool_calls": sum(
                    e["event_type"] == "request_projected"
                    and (e.get("payload") or {}).get("role") == "tool"
                    for e in events
                ),
                "related_job": compare,
            },
            "host_state": safe_fields(self.state(subject["job_id"])),
            "host_observations": [
                {
                    "state": safe_fields(s),
                    "evidence_refs": [
                        self.ref("states", i) if "states" in self.data else self.ref("status")
                    ],
                }
                for i, s in enumerate(self.states)
                if s.get("job_id") == subject["job_id"]
            ],
            "report_summary": report_summary,
            "related_evidence": related_evidence,
            "timeline": timeline,
            "physical_call_states": call_states,
            "context_checks": {
                boundary: result(
                    aggregate(p["verdict"] for p in selected_pairs), calls=selected_pairs
                ),
                "required_content_complete": content,
                "source_isolation_satisfied": isolation,
            },
            "business_acceptance": acceptance,
            "evaluations": {
                "semantic_verdict": self.data.get("semantic_verdict", "NOT_RUN"),
                "source_workflow_verdict": self.data.get("workflow_verdict"),
                "source_assessments": safe_assessments(self.data.get("assessment_components", [])),
                "scope": "original_archive_evaluations_no_reassessment",
            },
            "gaps": self.gaps,
            "findings": self.findings,
        }


def render(diagnosis):
    """The Markdown view uses only the redacted diagnosis, never the raw archive."""
    subject = diagnosis["subject"]
    lines = [
        "# 离线归档诊断",
        "",
        f"- Review：`{subject['review_id']}`",
        f"- Job：`{subject['job_id']}`",
        f"- Input：`{subject['input_revision_id']}`",
        f"- Report：`{subject['report_revision_id'] or '无'}`",
        "",
        "## 宿主及检查结果",
        "",
        f"宿主状态：`{canonical(diagnosis['host_state'])}`",
        "",
        "| 检查 | 结果 |",
        "| --- | --- |",
    ]
    for name, check in diagnosis["context_checks"].items():
        lines.append(f"| {name} | {check['verdict']} |")
    lines += [
        "",
        "正文完整性仅按声明义务取证；未覆盖案例材料列为无法判断。",
        "",
        "## 时间线",
        "",
        "| 序号 | 事件 | 调用 | 证据 |",
        "| --- | --- | --- | --- |",
    ]
    for item in diagnosis["timeline"]:
        lines.append(
            f"| {item['event_seq']} | {item['event_type']} | "
            f"{item['call_id'] or '—'} | {item['evidence_state']} |"
        )
    for title, key in (
        ("报告及冻结采用摘要", "report_summary"),
        ("宿主状态历史", "host_observations"),
        ("明确引用的前置证据", "related_evidence"),
        ("上下文逐项证据", "context_checks"),
        ("物理收尾与用量", "physical_call_states"),
        ("业务采用", "business_acceptance"),
        ("原评价", "evaluations"),
        ("缺口", "gaps"),
        ("诊断发现", "findings"),
        ("来源范围", "source_coverage"),
    ):
        lines += [
            "",
            f"## {title}",
            "",
            "```json",
            json.dumps(
                diagnosis[key], ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
            ),
            "```",
        ]
    return "\n".join(lines) + "\n"


def export(diagnosis, output):
    output = Path(output).absolute()
    if output.exists():
        raise DiagnosisError("OUTPUT_ALREADY_EXISTS", 3)
    try:
        with tempfile.TemporaryDirectory(prefix=".diagnosis-", dir=output.parent) as temp:
            stage = Path(temp) / "complete"
            stage.mkdir()
            (stage / "diagnosis.json").write_text(canonical(diagnosis) + "\n", encoding="utf-8")
            (stage / "diagnosis.md").write_text(render(diagnosis), encoding="utf-8")
            # Windows rename refuses an existing destination. Never overwrite prior output.
            if output.exists():
                raise DiagnosisError("OUTPUT_ALREADY_EXISTS", 3)
            os.rename(stage, output)
    except OSError:
        raise DiagnosisError("OUTPUT_IO_ERROR", 3) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读 F01/B2 历史归档诊断")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-revision-id")
    parser.add_argument("--review-id")
    parser.add_argument("--job-id")
    parser.add_argument("--trial-ledger")
    parser.add_argument("--b2-export-source")
    parser.add_argument("--compare-review-id")
    parser.add_argument("--compare-job-id")
    args = parser.parse_args(argv)
    try:
        require(
            bool(args.compare_review_id) == bool(args.compare_job_id), "COMPARISON_PAIR_REQUIRED", 2
        )
        raw = read_bytes(args.evidence, 16 * 1024**2)
        data, ledger, sources = parse(raw), [], {"evidence_sha256": digest(raw)}
        if args.trial_ledger:
            journal = read_bytes(args.trial_ledger, 8 * 1024**2)
            # Empty lines keep physical JSONL line numbering intact.
            ledger = [parse(line) if line.strip() else {} for line in journal.splitlines()]
            require(all(isinstance(row, dict) for row in ledger))
            sources["trial_ledger_sha256"] = digest(journal)
        order_source = None
        if args.b2_export_source:
            order_source = digest(read_bytes(args.b2_export_source, 1024**2))
        archive = Archive(
            data,
            source=str(Path(args.evidence).absolute()),
            ledger=ledger,
            order_source=order_source,
        )
        subject = archive.select(
            report_id=args.report_revision_id, review_id=args.review_id, job_id=args.job_id
        )
        compare = (
            archive.select(
                review_id=args.compare_review_id, job_id=args.compare_job_id, failure=False
            )
            if args.compare_review_id
            else None
        )
        diagnosis = archive.diagnose(subject, compare)
        diagnosis["source_coverage"].update(sources)
        if args.trial_ledger:
            diagnosis["source_coverage"]["trial_ledger_path"] = str(
                Path(args.trial_ledger).absolute()
            )
        export(diagnosis, args.output)
        print(canonical({"status": "EXPORTED", "output": str(Path(args.output).absolute())}))
        return 0
    except DiagnosisError as error:
        print(canonical({"error": error.code, "candidates": error.candidates}), file=sys.stderr)
        return error.exit_code
    except (ValueError, KeyError, TypeError, IndexError, RecursionError):
        print(canonical({"error": "INVALID_ARCHIVE_SHAPE"}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
