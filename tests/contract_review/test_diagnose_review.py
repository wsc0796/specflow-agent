"""Offline diagnosis counterexamples; expected facts are built independently of the reader."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from specflow.contract_review.common import canonical, digest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "contract_review"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if "review_evidence" not in sys.modules:
    load("review_evidence", "review_evidence.py")
diag = load("diagnose_review_ab", "diagnose_review.py")


def event(archive, review, job, iid, kind, payload, *, call=None, seq=None, cause=None):
    sequence = seq or (
        1
        + max(
            (e["event_seq"] for e in archive["events"].values() if e["review_id"] == review),
            default=0,
        )
    )
    eid = f"evt_{review}_{sequence}"
    value = {
        "event_id": eid,
        "event_seq": sequence,
        "event_type": kind,
        "review_id": review,
        "input_revision_id": iid,
        "job_id": job,
        "payload": copy.deepcopy(payload),
        "payload_hash": digest(payload),
        "payload_available": True,
        "evidence_integrity": "complete",
        "missing_evidence": [],
        "caused_by_event_id": cause,
        "occurred_at": "2026-11-05T01:00:00Z",
        "recorded_at": "2026-11-05T01:00:00Z",
    }
    if call:
        value.update(call_id=call, logical_call_id=f"logical_{call}")
    archive["events"][eid] = value
    return value


def empty():
    return {
        "schema_version": "cr02-b1-evidence.v1",
        "collection_complete": True,
        "evidence_status": "COMPLETE",
        "semantic_verdict": "NOT_RUN",
        "workflow_verdict": "PASS",
        "events": {},
        "jobs": {},
        "inputs": {},
        "reports": {},
        "states": [],
        "request_projections": {},
        "test_store_inputs": {},
        "test_store_calls": [],
        "adapter_delivery": [],
        "test_store_resolutions": [],
        "mutations": [],
        "gaps": [],
    }


def subject(archive, suffix="b", *, review=None, answers=()):
    review, job, iid, report, call = (
        review or f"cr_{suffix}",
        f"job_{suffix}",
        f"input_{suffix}",
        f"report_{suffix}",
        f"call_{suffix}",
    )
    rule = {
        "adoption_id": f"adopt_{suffix}",
        "input_revision_id": iid,
        "target_id": "target_1",
        "origin": {"kind": "project_decision"},
        "disposition": "adopted",
        "body": "RULE_PRIVATE_BODY_queued_only",
        "body_hash": digest(b"RULE_PRIVATE_BODY_queued_only"),
    }
    authority = {
        "adoption_id": f"authority_{suffix}",
        "input_revision_id": iid,
        "origin": {"kind": "authority_binding"},
        "disposition": "adopted",
        "body_ref": {"source_id": "source_1", "selector": {"kind": "full"}},
        "body_hash": digest(b"AUTHORITY_PRIVATE_BODY"),
    }
    frozen = {
        "input_revision_id": iid,
        "adoption_records": [rule, authority],
        "resolutions": list(answers),
        "target_manifest": [],
        "check_manifest": [],
        "execution_profile": {},
        "original_request": {"request": "REQUEST_PRIVATE_BODY"},
    }
    frozen["input_hash"] = digest(frozen)
    data = {
        "request": "REQUEST_PRIVATE_BODY",
        "adoption_records": copy.deepcopy([rule, authority]),
        "resolutions": copy.deepcopy(list(answers)),
        "rule_materials": [
            {"adoption_id": rule["adoption_id"], "body": rule["body"]},
            {"source_ref": authority["body_ref"], "body": "AUTHORITY_PRIVATE_BODY"},
        ],
        "observations": [
            {
                "observation_id": "obs_1",
                "body": {"text": "SOURCE_PRIVATE_BODY"},
                "source_refs": [authority["body_ref"]],
            }
        ],
    }
    wire = {
        "model": "controlled",
        "messages": [
            {"role": "system", "content": "SYSTEM_PRIVATE_BODY"},
            {"role": "user", "content": canonical(data)},
        ],
        "temperature": 0,
        "max_tokens": 100,
        "response_format": {"type": "json_object"},
    }
    projection = {
        "role": "analysis",
        "payload": wire,
        "input_hash": frozen["input_hash"],
        "projection_hash": digest(wire),
        "child_task_id": None,
        "material_entries": [],
    }
    e = event(archive, review, job, iid, "request_projected", projection, call=call)
    archive["jobs"][job] = {"review_id": review, "input_id": iid, "events_complete": True}
    archive["inputs"][iid] = {"review_id": review}
    archive["test_store_inputs"][iid] = frozen
    archive["request_projections"][e["event_id"]] = copy.deepcopy(projection)
    archive["test_store_calls"].append(
        {
            "call_id": call,
            "job_id": job,
            "review_id": review,
            "input_id": iid,
            "kind": "model",
            "remote_outcome": "known",
            "projection": copy.deepcopy(projection),
            "local_io_state": "quiesced",
            "acceptance": {"accepted": True},
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }
    )
    archive["adapter_delivery"].append(copy.deepcopy(wire))
    archive["reports"][report] = {
        "json": {
            "report_revision_id": report,
            "review_id": review,
            "input_revision_id": iid,
            "job_id": job,
            "rules": [rule],
            "adopted_ruleset_version": 1,
            "payload": {},
        }
    }
    event(archive, review, job, iid, "report_committed", {"report_revision_id": report})
    archive["states"].append(
        {
            "review_id": review,
            "job_id": job,
            "current_input_revision_id": iid,
            "current_report_revision_id": report,
            "status": "completed",
            "job_status": "completed",
            "error_code": None,
        }
    )
    return {
        "review_id": review,
        "job_id": job,
        "input_revision_id": iid,
        "report_revision_id": report,
        "call_id": call,
    }


def wire_change(archive, call, change):
    index = next(i for i, c in enumerate(archive["test_store_calls"]) if c["call_id"] == call)
    wire = archive["adapter_delivery"][index]
    data = json.loads(wire["messages"][1]["content"])
    change(data)
    wire["messages"][1]["content"] = canonical(data)
    c = archive["test_store_calls"][index]
    c["projection"]["payload"] = copy.deepcopy(wire)
    c["projection"]["projection_hash"] = digest(wire)
    e = next(
        e
        for e in archive["events"].values()
        if e.get("call_id") == call and e["event_type"] == "request_projected"
    )
    e["payload"] = copy.deepcopy(c["projection"])
    e["payload_hash"] = digest(e["payload"])
    archive["request_projections"][e["event_id"]] = copy.deepcopy(e["payload"])


def diagnose(archive, selected, *, order=True, compare=None, ledger=()):
    reader = diag.Archive(
        archive, order_source=diag.B2_ORDER_SOURCE if order else None, ledger=ledger
    )
    chosen = reader.select(
        report_id=selected.get("report_revision_id"),
        review_id=selected["review_id"],
        job_id=selected["job_id"],
    )
    other = (
        reader.select(review_id=compare["review_id"], job_id=compare["job_id"], failure=False)
        if compare
        else None
    )
    return reader.diagnose(chosen, other)


def make_failed(archive, selected, code="ACTION_PROTOCOL_ERROR"):
    del archive["reports"][selected["report_revision_id"]]
    archive["events"] = {
        k: e
        for k, e in archive["events"].items()
        if not (e["job_id"] == selected["job_id"] and e["event_type"] == "report_committed")
    }
    selected["report_revision_id"] = None
    state = next(s for s in archive["states"] if s["job_id"] == selected["job_id"])
    state.update(
        status="failed", job_status="failed", current_report_revision_id=None, error_code=code
    )
    return event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "job_failed",
        {"error_code": code},
    )


@pytest.fixture
def case():
    archive = empty()
    selected = subject(archive)
    return archive, selected


def test_scope_and_default_output_do_not_claim_full_source_coverage(case):
    archive, selected = case
    d = diagnose(archive, selected)
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "PASS"
    content = d["context_checks"]["required_content_complete"]
    assert content["verdict"] == "UNDETERMINED"
    assert content["full_case_coverage"] == "UNDETERMINED"
    assert d["evaluations"]["semantic_verdict"] == "NOT_RUN"
    assert "PRIVATE_BODY" not in canonical(d)
    assert "PRIVATE_BODY" not in diag.render(d)


@pytest.mark.parametrize("remove_everywhere", [False, True], ids=["AC02a", "AC02b"])
def test_joint_omission_distinguishes_channel_from_body(case, remove_everywhere):
    archive, selected = case
    original_frozen = copy.deepcopy(archive["test_store_inputs"])

    def omit(data):
        data["rule_materials"] = []
        if remove_everywhere:
            data["adoption_records"][0].pop("body")

    wire_change(archive, selected["call_id"], omit)
    d = diagnose(archive, selected)
    assert archive["test_store_inputs"] == original_frozen
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "PASS"
    content = d["context_checks"]["required_content_complete"]
    assert content["verdict"] == "FAIL"
    obligations = {o["obligation"]: o for o in content["calls"][0]["obligations"]}
    assert obligations["rule_material_channel"]["verdict"] == "FAIL"
    body = obligations["required_body_present"]
    assert body["verdict"] == ("FAIL" if remove_everywhere else "PASS")
    assert bool(body["body_locations"]) is not remove_everywhere


@pytest.mark.parametrize("damage", ["unknown_order", "truncated", "extra_call"])
def test_pairing_insufficient_evidence_never_becomes_pass(case, damage):
    archive, selected = case
    if damage == "truncated":
        archive["adapter_delivery"] = []
    if damage == "extra_call":
        archive["test_store_calls"] = []
    d = diagnose(archive, selected, order=damage != "unknown_order")
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "UNDETERMINED"
    assert not d["source_coverage"]["diagnostic_collection_complete"]


def test_entire_wire_fields_are_compared_and_known_mismatch_is_fail(case):
    archive, selected = case
    archive["adapter_delivery"][0]["temperature"] = True
    d = diagnose(archive, selected)
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "FAIL"


def test_pair_full_export_before_selecting_old_job(case):
    archive, old = case
    new = subject(archive, "new", review=old["review_id"])
    archive["reports"][new["report_revision_id"]]["json"]["adopted_ruleset_version"] = 2
    archive["adapter_delivery"][1]["max_tokens"] = 99
    d = diagnose(archive, old)
    assert d["subject"]["input_revision_id"] == old["input_revision_id"]
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "PASS"
    assert len(d["timeline"]) == 2
    assert {g["code"] for g in d["gaps"]} == {"INDEPENDENT_CASE_MATERIALS_NOT_CAPTURED"}


@pytest.mark.parametrize("damage", ["report", "job", "foreign_event", "event_key", "input"])
def test_ownership_errors_refuse_before_export(case, damage):
    archive, selected = case
    if damage == "report":
        archive["reports"][selected["report_revision_id"]]["json"]["review_id"] = "cr_foreign"
    elif damage == "job":
        archive["test_store_calls"][0]["job_id"] = "job_foreign"
    elif damage == "foreign_event":
        other = subject(archive, "other")
        e = next(e for e in archive["events"].values() if e["job_id"] == selected["job_id"])
        e["caused_by_event_id"] = next(
            e["event_id"] for e in archive["events"].values() if e["job_id"] == other["job_id"]
        )
    elif damage == "event_key":
        key = next(iter(archive["events"]))
        archive["events"]["evt_foreign"] = archive["events"].pop(key)
    else:
        archive["inputs"][selected["input_revision_id"]]["review_id"] = "cr_foreign"
    with pytest.raises(diag.DiagnosisError) as error:
        diagnose(archive, selected)
    assert error.value.exit_code == 2


def test_wrong_report_job_selector_and_ambiguous_failure(case):
    archive, selected = case
    with pytest.raises(diag.DiagnosisError, match="REPORT_JOB_MISMATCH"):
        diag.Archive(archive).select(report_id=selected["report_revision_id"], job_id="job_wrong")
    make_failed(archive, selected)
    reader = diag.Archive(archive)
    assert reader.select(review_id=selected["review_id"])["job_id"] == selected["job_id"]
    other = subject(archive, "other", review=selected["review_id"])
    make_failed(archive, other)
    with pytest.raises(diag.DiagnosisError, match="FAILED_JOB_SELECTION_REQUIRED") as error:
        diag.Archive(archive).select(review_id=selected["review_id"])
    assert len(error.value.candidates) == 2


@pytest.mark.parametrize(
    "damage", ["payload_hash", "cached_projection", "frozen_hash", "missing_frozen"]
)
def test_integrity_conflict_or_absence_does_not_certify_content(case, damage):
    archive, selected = case
    if damage == "payload_hash":
        next(iter(archive["events"].values()))["payload_hash"] = "0" * 64
    elif damage == "cached_projection":
        next(iter(archive["request_projections"].values()))["payload"]["max_tokens"] = 1
    elif damage == "frozen_hash":
        archive["test_store_inputs"][selected["input_revision_id"]]["input_hash"] = "0" * 64
    else:
        archive.pop("test_store_inputs")
    d = diagnose(archive, selected)
    assert d["context_checks"]["required_content_complete"]["verdict"] == "UNDETERMINED"
    assert d["gaps"]


def h03():
    archive = empty()
    archive["scenario"] = "CR02-H03"
    a0 = subject(archive, "a0", review="cr_a")
    answer = {
        "resolution_id": "res_A",
        "review_id": "cr_a",
        "input_revision_id": a0["input_revision_id"],
        "report_revision_id": a0["report_revision_id"],
        "answer": {"text": "ANSWER_PRIVATE_BODY_v1", "scope": "this_review"},
    }
    a1 = subject(archive, "a1", review="cr_a", answers=[answer])
    b = subject(archive)
    archive["test_store_resolutions"] = [
        {
            "id": "res_A",
            "review_id": "cr_a",
            "input_id": a0["input_revision_id"],
            "report_id": a0["report_revision_id"],
            "body": canonical(answer),
        }
    ]
    archive["mutations"] = [
        {
            "review_id": "cr_a",
            "status": 202,
            "response": {
                "job_id": a1["job_id"],
                "input_revision_id": a1["input_revision_id"],
                "accepted_resolution_ids": ["res_A"],
            },
        }
    ]
    return archive, a1, b, answer


def test_h03_clean_input_with_wrong_output_is_still_isolated():
    archive, a1, b, _ = h03()
    archive["reports"][b["report_revision_id"]]["json"]["payload"] = {
        "judgment_status": "legitimate_version_difference"
    }
    d = diagnose(archive, b, compare=a1)
    assert d["context_checks"]["source_isolation_satisfied"]["verdict"] == "PASS"
    assert d["evaluations"]["semantic_verdict"] == "NOT_RUN"
    assert "ANSWER_PRIVATE_BODY" not in canonical(d)


@pytest.mark.parametrize("place", ["wire", "frozen"])
def test_h03_answer_in_correctly_owned_b_is_failure(place):
    archive, a1, b, answer = h03()
    if place == "wire":
        wire_change(archive, b["call_id"], lambda data: data.update(resolutions=[answer]))
    else:
        frozen = archive["test_store_inputs"][b["input_revision_id"]]
        frozen["resolutions"] = [answer]
        frozen["input_hash"] = digest({k: v for k, v in frozen.items() if k != "input_hash"})
    d = diagnose(archive, b, compare=a1)
    isolation = d["context_checks"]["source_isolation_satisfied"]
    assert isolation["verdict"] == "FAIL"
    assert isolation["answers"][0]["evidence_refs"]


@pytest.mark.parametrize(
    "missing", ["comparison", "stored_answer", "A_positive", "B_call", "B_frozen"]
)
def test_h03_incomplete_control_is_undetermined(missing):
    archive, a1, b, _ = h03()
    if missing == "stored_answer":
        archive["test_store_resolutions"] = []
    elif missing == "A_positive":
        wire_change(archive, a1["call_id"], lambda data: data.update(resolutions=[]))
    elif missing == "B_call":
        archive["adapter_delivery"].pop()
    elif missing == "B_frozen":
        del archive["test_store_inputs"][b["input_revision_id"]]
    d = diagnose(archive, b, compare=None if missing == "comparison" else a1)
    assert d["context_checks"]["source_isolation_satisfied"]["verdict"] == "UNDETERMINED"


def test_known_fail_survives_late_history_gap(case):
    archive, selected = case
    wire_change(archive, selected["call_id"], lambda data: data.update(rule_materials=[]))
    archive["gaps"] = [{"code": "READ_FAILED", "private": "PRIVATE_BODY"}]
    archive["collection_complete"] = False
    d = diagnose(archive, selected)
    assert d["context_checks"]["required_content_complete"]["verdict"] == "FAIL"
    assert len(d["timeline"]) == 2
    assert not d["source_coverage"]["diagnostic_collection_complete"]
    assert d["source_coverage"]["source_evidence_status"] == "COMPLETE"


def test_missing_explicit_cause_but_not_numeric_sequence_gap(case):
    archive, selected = case
    e = list(archive["events"].values())[-1]
    e["event_seq"] = 20
    assert {g["code"] for g in diagnose(archive, selected)["gaps"]} == {
        "INDEPENDENT_CASE_MATERIALS_NOT_CAPTURED"
    }
    e["caused_by_event_id"] = "evt_missing"
    assert any(g["code"] == "CAUSAL_EVENT_MISSING" for g in diagnose(archive, selected)["gaps"])


@pytest.mark.parametrize("stage", [None, "context_build"])
def test_budget_stage_requires_explicit_evidence(case, stage):
    archive, selected = case
    e = make_failed(archive, selected, "BUDGET_EXHAUSTED")
    if stage:
        e["payload"]["stage"] = stage
        e["payload_hash"] = digest(e["payload"])
    d = diagnose(archive, selected)
    f = next(f for f in d["findings"] if f["code"] == "BUDGET_FAILURE")
    assert f["stage"] == (stage or "UNDETERMINED")


def test_unknown_late_cleanup_and_parent_rejection_remain_separate(case):
    archive, selected = case
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "call_unknown",
        {"remote_outcome": "unknown", "status": "UNKNOWN"},
        call=selected["call_id"],
    )
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "result_rejected",
        {"code": "CALL_RESULT_UNKNOWN"},
        call=selected["call_id"],
    )
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "call_quiesced",
        {"local_io_state": "quiesced", "usage": {"input_tokens": 8, "output_tokens": 5}},
        call=selected["call_id"],
    )
    child = event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "child_result_available",
        {"child_result_ref": "child_1", "status": "completed"},
    )
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "child_result_reviewed",
        {"child_result_ref": "child_1", "disposition": "rejected"},
        cause=child["event_id"],
    )
    d = diagnose(archive, selected)
    assert any(t["state"].get("status") == "UNKNOWN" for t in d["timeline"])
    assert any(t["state"].get("usage", {}).get("input_tokens") == 8 for t in d["timeline"])
    assert any(t["state"].get("disposition") == "rejected" for t in d["business_acceptance"])
    assert any(t["state"].get("status") == "completed" for t in d["timeline"])


def f01(case):
    archive, selected = copy.deepcopy(case)
    e = next(iter(archive["events"].values()))
    wire = copy.deepcopy(e["payload"]["payload"])
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "action_proposed",
        {
            "action": "submit_report",
            "report": {
                "findings": [{"verification_evidence_refs": ["obs_1"]}],
                "acceptance_items": [{"evidence_refs": ["obs_1"]}],
            },
        },
        call=selected["call_id"],
    )
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "action_rejected",
        {"code": "ACTION_SCHEMA_INVALID"},
        call=selected["call_id"],
    )
    make_failed(archive, selected)
    archive["events"] = list(archive["events"].values())
    ledger = [
        {
            "event": "reserved_before_adapter_http",
            "trial_call_id": "trial_1",
            "payload": wire,
            "wire_hash": digest(wire),
        },
        {"event": "http_transport_entered", "trial_call_id": "trial_1"},
    ]
    return archive, selected, ledger


def test_f01_reconstructed_field_fact_is_not_host_error_text(case):
    archive, selected, ledger = f01(case)
    d = diagnose(archive, selected, ledger=ledger)
    assert d["subject"]["report_revision_id"] is None
    assert d["context_checks"]["projection_matches_transport"]["verdict"] == "PASS"
    assert d["host_state"]["error_code"] == "ACTION_PROTOCOL_ERROR"
    facts = [f for f in d["findings"] if f["code"] == "OBSERVATION_IN_EXTERNAL_EVIDENCE_FIELD"]
    assert len(facts) == 2
    assert all(f["attribution"] == "reconstructed_structural_fact" for f in facts)
    assert all(len(f["evidence_refs"]) == 3 for f in facts)
    rejected = next(f for f in d["findings"] if f["code"] == "HOST_ACTION_REJECTED")
    assert rejected["host_error"] == {"code": "ACTION_SCHEMA_INVALID"}


@pytest.mark.parametrize("damage", ["duplicate", "missing_enter", "hash", "coverage"])
def test_f01_ambiguous_or_incomplete_pair_never_passes(case, damage):
    archive, selected, ledger = f01(case)
    if damage == "duplicate":
        ledger.append(copy.deepcopy(ledger[0]))
    elif damage == "missing_enter":
        ledger.pop()
    elif damage == "hash":
        ledger[0]["wire_hash"] = "0" * 64
    else:
        archive["collection_complete"] = False
    d = diagnose(archive, selected, ledger=ledger)
    assert d["context_checks"]["projection_matches_transport"]["verdict"] == "UNDETERMINED"


def cli_file(tmp_path, archive):
    file = tmp_path / "evidence.json"
    file.write_text(canonical(archive), encoding="utf-8")
    return file


def test_cli_publishes_both_formats_and_never_overwrites(case, tmp_path):
    archive, selected = case
    archive["untrusted_path"] = str(tmp_path / "must-not-read")
    file = cli_file(tmp_path, archive)
    before = file.read_bytes()
    output = tmp_path / "diagnosis"
    args = [
        "--evidence",
        str(file),
        "--report-revision-id",
        selected["report_revision_id"],
        "--output",
        str(output),
    ]
    assert diag.main(args) == 0
    result = json.loads((output / "diagnosis.json").read_text("utf-8"))
    assert (output / "diagnosis.md").read_text("utf-8") == diag.render(result)
    assert file.read_bytes() == before
    assert diag.main(args) == 3


@pytest.mark.parametrize("raw", ['{"events":{},"events":[]}', '{"x":NaN}', "{bad", "[]"])
def test_strict_json_failure_leaves_no_output(tmp_path, raw):
    file = tmp_path / "bad.json"
    file.write_text(raw)
    output = tmp_path / "out"
    assert diag.main(["--evidence", str(file), "--review-id", "cr_b", "--output", str(output)]) == 3
    assert not output.exists()


def test_output_failure_does_not_publish_partial_directory(case, tmp_path, monkeypatch):
    archive, selected = case
    d = diagnose(archive, selected)
    monkeypatch.setattr(diag, "render", lambda _: (_ for _ in ()).throw(OSError("simulated")))
    with pytest.raises(diag.DiagnosisError, match="OUTPUT_IO_ERROR"):
        diag.export(d, tmp_path / "out")
    assert not list(tmp_path.iterdir())


def test_bounded_read_rejects_before_parsing(tmp_path):
    p = tmp_path / "large"
    p.write_bytes(b"12345")
    with pytest.raises(diag.DiagnosisError, match="INPUT_SIZE_LIMIT"):
        diag.read_bytes(p, 4)


@pytest.mark.parametrize("identifiable", [True, False])
def test_unknown_body_only_snapshot_keeps_outcome_and_unknown_usage(case, identifiable):
    archive, selected = case
    make_failed(archive, selected, "PROVIDER_TIMEOUT")
    call = archive["test_store_calls"][0]
    call.update(remote_outcome="unknown", usage={"input_tokens": None, "output_tokens": None})
    call.pop("call_id")
    call.pop("job_id")
    if identifiable:
        call["projection"]["projection_id"] = "projection_1"
        e = next(iter(archive["events"].values()))
        e["payload"]["projection_id"] = "projection_1"
        e["payload_hash"] = digest(e["payload"])
        archive["request_projections"][e["event_id"]] = copy.deepcopy(e["payload"])
    archive.pop("adapter_delivery")
    archive.pop("test_store_inputs")
    d = diagnose(archive, selected)
    physical = d["physical_call_states"][0]
    assert physical["state"]["remote_outcome"] == "unknown"
    assert physical["state"]["usage"]["input_tokens"] is None
    assert physical["call_id"] == (selected["call_id"] if identifiable else None)
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "UNDETERMINED"


def test_report_semantics_and_rule_versions_are_retained_without_body(case):
    archive, selected = case
    r = archive["reports"][selected["report_revision_id"]]["json"]
    r["payload"] = {
        "findings": [
            {
                "id": "finding_1",
                "judgment_status": "insufficient_evidence",
                "claim": "DO_NOT_EXPORT_PRIVATE_BODY",
            }
        ]
    }
    d = diagnose(archive, selected)
    assert d["report_summary"]["adopted_ruleset_version"] == 1
    assert d["report_summary"]["findings"][0]["judgment_status"] == "insufficient_evidence"
    assert d["report_summary"]["rules"][0]["disposition"] == "adopted"
    assert "PRIVATE_BODY" not in canonical(d)


@pytest.mark.parametrize("missing", ["projection_detail", "commit_event"])
def test_missing_required_event_keeps_exportable_object(case, missing):
    archive, selected = case
    if missing == "projection_detail":
        e = next(iter(archive["events"].values()))
        e["payload"] = None
        e["payload_available"] = False
    else:
        archive["events"] = {
            k: e for k, e in archive["events"].items() if e["event_type"] != "report_committed"
        }
    d = diagnose(archive, selected)
    assert not d["source_coverage"]["diagnostic_collection_complete"]
    assert d["report_summary"] is not None


def test_actual_late_event_shape_keeps_early_unknown_snapshot(case):
    archive, selected = case
    make_failed(archive, selected, "CALL_RESULT_UNKNOWN")
    archive["states"][0]["last_call"] = {
        "call_id": selected["call_id"],
        "status": "UNKNOWN",
        "local_io_state": "unconfirmed",
        "remote_outcome": "unknown",
    }
    call = archive["test_store_calls"][0]
    call.update(
        status="UNKNOWN",
        acceptance=None,
        remote_outcome="unknown",
        usage={"input_tokens": 3, "output_tokens": 4},
    )
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "call_quiesced",
        {
            "execution_instance_id": "io_late",
            "local_io_state": "quiesced",
            "usage": {"input_tokens": 3, "output_tokens": 4},
            "evidence": "wrapper_thread_exited",
        },
        call=selected["call_id"],
    )
    d = diagnose(archive, selected)
    assert d["host_observations"][0]["state"]["last_call"]["status"] == "UNKNOWN"
    assert d["physical_call_states"][0]["state"]["status"] == "UNKNOWN"
    assert d["physical_call_states"][0]["state"]["usage"]["input_tokens"] == 3
    assert d["host_state"]["job_status"] == "failed"


def test_jobless_answer_event_is_linked_without_including_other_jobs(case):
    archive, selected = case
    old = subject(archive, "old", review=selected["review_id"])
    answer = event(
        archive,
        selected["review_id"],
        None,
        old["input_revision_id"],
        "resolutions_recorded",
        {"records": [], "next_job_id": selected["job_id"]},
    )
    d = diagnose(archive, selected)
    assert any(r["event_id"] == answer["event_id"] for r in d["related_evidence"])
    assert len(d["timeline"]) == 2


@pytest.mark.parametrize("omit", [False, True])
def test_fixed_review_requires_cited_material_channel_from_prior_candidate(case, omit):
    archive, selected = case
    candidate = {
        "coverage": [{"source_refs": [{"source_id": "source_1", "selector": {"kind": "full"}}]}],
        "findings": [],
        "check_results": [],
        "work_items": [],
        "acceptance_items": [],
        "questions": [],
    }
    call = archive["test_store_calls"][0]
    call["projection"]["role"] = "review"
    archive["events"] = {}
    archive["request_projections"] = {}
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "action_proposed",
        {"action": "submit_report", "report": candidate},
        call="call_prior",
    )
    e = event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "request_projected",
        call["projection"],
        call=selected["call_id"],
    )
    archive["request_projections"][e["event_id"]] = copy.deepcopy(e["payload"])
    event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "report_committed",
        {"report_revision_id": selected["report_revision_id"]},
    )
    wire_change(
        archive,
        selected["call_id"],
        lambda data: data.update(
            candidate_report=candidate,
            candidate_report_hash=digest(candidate),
            cited_materials=[]
            if omit
            else [
                {
                    "source_ref": candidate["coverage"][0]["source_refs"][0],
                    "body": "SOURCE_PRIVATE_BODY",
                }
            ],
        ),
    )
    d = diagnose(archive, selected)
    checks = d["context_checks"]["required_content_complete"]["calls"][0]["obligations"]
    assert next(c for c in checks if c["obligation"] == "candidate_origin")["verdict"] == "PASS"
    assert next(c for c in checks if c["obligation"] == "candidate_cited_source")["verdict"] == (
        "FAIL" if omit else "UNDETERMINED"
    )


def test_tool_projection_is_separate_and_bad_body_is_not_exempt(case):
    archive, selected = case
    tool = event(
        archive,
        selected["review_id"],
        selected["job_id"],
        selected["input_revision_id"],
        "request_projected",
        {
            "role": "tool",
            "payload": {"tool": "read_source", "arguments": {}},
            "projection_hash": digest({"tool": "read_source", "arguments": {}}),
        },
        call="call_tool",
    )
    d = diagnose(archive, selected)
    assert d["source_coverage"]["model_calls"] == 1
    assert d["source_coverage"]["tool_calls"] == 1
    assert d["context_checks"]["projection_matches_adapter"]["verdict"] == "PASS"
    tool["payload"]["payload"] = {"tool": "read_source", "arguments": "invalid"}
    tool["payload"]["projection_hash"] = digest(tool["payload"]["payload"])
    tool["payload_hash"] = digest(tool["payload"])
    d = diagnose(archive, selected)
    assert any(g["code"] == "PROJECTED_REQUEST_BODY_INVALID" for g in d["gaps"])


def test_f01_one_transport_identity_cannot_certify_two_physical_calls(case):
    archive, selected = case
    subject(archive, "other")
    archive, selected, ledger = f01((archive, selected))
    other_wire = archive["adapter_delivery"][1]
    ledger.insert(
        1,
        {
            "event": "reserved_before_adapter_http",
            "trial_call_id": "trial_1",
            "payload": other_wire,
            "wire_hash": digest(other_wire),
        },
    )
    d = diagnose(archive, selected, ledger=ledger)
    assert d["context_checks"]["projection_matches_transport"]["verdict"] == "UNDETERMINED"


def test_auto_failure_selection_rejects_explicit_gap_even_if_complete_flag_is_stale(case):
    archive, selected = case
    make_failed(archive, selected)
    archive["gaps"] = [{"code": "READ_FAILED"}]
    with pytest.raises(diag.DiagnosisError, match="FAILED_JOB_SELECTION_REQUIRED"):
        diag.Archive(archive).select(review_id=selected["review_id"])
    assert diagnose(archive, selected)["host_state"]["job_status"] == "failed"
