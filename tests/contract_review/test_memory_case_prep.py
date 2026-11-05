"""B2 controlled API/worker evidence; model semantics deliberately remain NOT_RUN."""

import copy
import importlib.util
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from test_decision_scope import project_adoptions, snapshot_input
from test_dynamic_workflow import read_action, reason

from specflow.api_security import ApiSecurity
from specflow.contract_review.profiles import dynamic_profile
from specflow.contract_review.provider import ProviderFailure
from specflow.main import create_app

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts/contract_review"


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ev = load_script("review_evidence", "review_evidence.py")
load_script("run_public_case_prep", "run_public_case_prep.py")
prep = load_script("b2_memory_case_prep", "run_memory_case_prep.py")


class MemoryAdapter:
    execution_mode = "test"

    def __init__(self, scenario, *, variant="normal"):
        self.scenario, self.variant = scenario, variant
        self.requests, self.outputs = [], []
        self.inputs = []

    def complete(self, payload):
        self.requests.append(copy.deepcopy(payload))
        data = json.loads(payload["messages"][1]["content"])
        input_id = data["adoption_records"][0]["input_revision_id"]
        if input_id not in self.inputs:
            self.inputs.append(input_id)
        if "candidate_report" in data:
            action = {
                "schema_version": "contract-review-review-result.v2",
                "type": "review_result",
                "candidate_report_hash": data["candidate_report_hash"],
                "outcome": "accept",
                "issues": [],
                "revision_feedback": "",
            }
        else:
            read_ids = {r["source_id"] for o in data["observations"] for r in o["source_refs"]}
            unread = [s for s in data["source_catalog"]["items"] if s["source_id"] not in read_ids]
            if unread:
                action = read_action(data, unread[0]["path"])
            else:
                action = {
                    "schema_version": "contract-review-action.v2.1",
                    "action": "submit_report",
                    "reason": reason("受控报告验证工程链路"),
                    "report": self.report(data),
                }
        self.outputs.append(copy.deepcopy(action))
        return {
            "content": json.dumps(action, ensure_ascii=False),
            "model": payload["model"],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }

    def report(self, data):
        findings, coverage, results, questions, uses = [], [], [], [], {}
        for index, target in enumerate(data["targets"]):
            tid, fid = target["target_id"], "finding_" + str(index)
            rules = [
                r
                for r in data["adoption_records"]
                if r["target_id"] == tid and r["disposition"] == "adopted"
            ]
            project = [r for r in rules if r["origin"]["kind"] == "project_decision"]
            h03 = self.scenario == "CR02-H03"
            cancel = target["endpoint"]["path"].endswith("/cancel")
            conflict = cancel and len(project) == 2 and not data["resolutions"]
            ambiguous = (
                h03
                and not data["resolutions"]
                and not (self.variant == "guess_v1" and len(self.inputs) == 3)
            )
            unknown = cancel and not project
            status = (
                "needs_decision"
                if conflict or ambiguous
                else "insufficient_evidence"
                if unknown
                else "legitimate_version_difference"
                if h03
                else "supported_deviation"
                if self.scenario == "CR02-R04"
                and cancel
                and "不允许queued例外" in project[0]["body"]
                else "no_deviation"
            )
            explanation = (
                "受控：queued允许与拒绝互斥，等待本次裁决。"
                if conflict
                else "受控：示例版本未知，请澄清。"
                if ambiguous
                else "受控：取消切片撤回，无有效规范；不推导反向禁止。"
                if unknown
                else "受控：示例按本次v1归属保留id，不判v2漂移。"
                if h03
                else "受控：queued实现允许，与新规则要求拒绝不符。"
                if status == "supported_deviation"
                else "受控：当前有效规则内静态无偏离，业务应用未执行。"
            )
            refs = [
                ref for observation in data["observations"] for ref in observation["source_refs"]
            ]
            refs = list({json.dumps(r, sort_keys=True): r for r in refs}.values())
            observations = [o["observation_id"] for o in data["observations"]]
            rule_refs = [r["adoption_id"] for r in rules]
            for rule in rules:
                uses[rule["adoption_id"]] = {
                    "adoption_id": rule["adoption_id"],
                    "usage": "conflict" if conflict else "support",
                    "explanation": explanation,
                }
            findings.append(
                {
                    "id": fid,
                    "target_ids": [tid],
                    "judgment_status": status,
                    "affected_artifacts": ["example" if h03 else "implementation"],
                    "labels": ["rule_conflict"] if conflict else [],
                    "claim": explanation,
                    "rule_refs": rule_refs,
                    "source_refs": refs,
                    "observation_refs": observations,
                    "verification_evidence_refs": [],
                    "execution_verification": "NOT_RUN",
                    "limitations": [explanation] if conflict or ambiguous or unknown else [],
                }
            )
            coverage.append(
                {
                    "target_id": tid,
                    "status": "partial" if unknown else "covered",
                    "source_refs": refs,
                    "missing_information": [explanation] if unknown else [],
                }
            )
            for check in data["check_manifest"]:
                if check["target_id"] == tid:
                    results.append(
                        {
                            "check_id": check["check_id"],
                            "status": "evidence_missing" if unknown else "checked",
                            "finding_ids": [fid],
                            "source_refs": refs,
                            "observation_refs": observations,
                            "missing_information": [explanation] if unknown else [],
                        }
                    )
            if conflict or ambiguous:
                questions.append(
                    {
                        "id": "question_" + str(index),
                        "kind": "rule_conflict" if conflict else "scope_choice",
                        "prompt": explanation,
                        "blocking": True,
                        "target_ids": [tid],
                        "finding_ids": [fid],
                        "work_item_ids": [],
                        "rule_refs": rule_refs,
                        "evidence_refs": [{"kind": "rule", "adoption_id": r} for r in rule_refs],
                        "why_blocking": explanation,
                        "options": [],
                        "allowed_answer_types": ["clarify"],
                    }
                )
        if self.variant == "duplicate" and questions:
            questions.append({**questions[0], "id": "question_duplicate"})
        if self.variant == "disallowed":
            for question in questions:
                question["allowed_answer_types"] = ["mark_insufficient"]
        return {
            "schema_version": "contract-review-report-payload.v2.1",
            "summary": "受控替身验证工程机制；真实语义未运行。",
            "coverage": coverage,
            "check_results": results,
            "rule_uses": list(uses.values()),
            "findings": findings,
            "questions": questions,
            "work_items": [],
            "acceptance_items": [],
            "adopted_child_result_refs": [],
            "limitations": ["未执行被查应用；不提供真实模型效果证据。"],
        }


@contextmanager
def local_client(tmp_path, adapter):
    runtime = tmp_path / ("runtime-" + uuid.uuid4().hex)
    runtime.mkdir()
    profile = dynamic_profile(prep.PROFILE, "controlled-test", delegation=False)
    profile["options"]["project_memory"] = True
    profile["model_timeout_seconds"] = 3.0
    app = create_app(
        f"sqlite:///{(runtime / 'reviews.sqlite').as_posix()}",
        runtime / "artifacts",
        ApiSecurity(api_key="b2-synthetic-key", allowed_repository_roots=(str(tmp_path),)),
        contract_review_profiles={prep.PROFILE: profile},
        contract_review_adapter=adapter,
    )
    with TestClient(app, headers={"X-API-Key": "b2-synthetic-key"}) as client:
        yield client, app.state.contract_reviews


def prepare(tmp_path, scenario):
    return prep.prepare_case(REPO, tmp_path / ("case-" + uuid.uuid4().hex), scenario)


def phase_report(evidence, phase):
    return evidence.data["reports"][evidence.data["phases"][phase]["current_report_revision_id"]][
        "json"
    ]


def run(tmp_path, scenario, *, variant="normal"):
    prepared = prepare(tmp_path, scenario)
    adapter = MemoryAdapter(scenario, variant=variant)
    with local_client(tmp_path, adapter) as (client, domain):
        evidence = prep.run_case(client, prepared)
        assert evidence.data["workflow_verdict"] == "PASS", evidence.data["blocking"] | {
            "gaps": evidence.data["gaps"],
            "states": evidence.data["states"][-1:],
        }
        frozen = {iid: snapshot_input(domain, iid) for iid in evidence.data["inputs"]}
        with domain.store.read() as conn:
            evidence.data["test_store_calls"] = [
                {"call_id": row["id"], "job_id": row["job_id"], **json.loads(row["body"])}
                for row in conn.exec_driver_sql(
                    "SELECT * FROM contract_review_calls ORDER BY rowid"
                ).mappings()
            ]
            evidence.data["test_store_resolutions"] = [
                dict(row)
                for row in conn.exec_driver_sql(
                    "SELECT * FROM contract_review_resolutions"
                ).mappings()
            ]
        evidence.data["test_store_inputs"] = frozen
        evidence.data["adapter_delivery"] = adapter.requests
        evidence.data["controlled_outputs"] = adapter.outputs
        check_delivery(evidence, adapter, frozen, prepared)
        evidence.data["assessment_components"] = [
            {
                "id": "AC10.payload_equality",
                "verdict": "PASS",
                "physical_model_calls": len(adapter.requests),
            },
            {"id": "AC10.required_bodies", "verdict": "PASS"},
            {"id": "AC10.no_leakage", "verdict": "PASS"},
        ]
        if scenario == "CR02-H03":
            check_isolation(evidence, adapter, frozen)
            evidence.data["assessment_components"].extend(
                [
                    {"id": "H03-3.isolation", "verdict": "PASS"},
                    {
                        "id": "H03-3.ambiguity",
                        "verdict": "NOT_RUN",
                        "controlled_fixture": "wrong_guess"
                        if variant == "guess_v1"
                        else "asks_again",
                    },
                ]
            )
        if os.environ.get("B2_EVIDENCE_ROOT"):
            output = Path(os.environ["B2_EVIDENCE_ROOT"]) / (
                scenario + "-" + variant + "-" + uuid.uuid4().hex[:8]
            )
            evidence.save(output)
        return evidence, adapter, frozen, prepared


@pytest.fixture(scope="module", autouse=True)
def counted_http_block():
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append("forbidden_http")
        raise AssertionError("Real HTTP is forbidden in B2")

    async def async_blocked(*args, **kwargs):
        blocked()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(httpx.HTTPTransport, "handle_request", blocked)
        patch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_blocked)
        yield attempts
        assert attempts == []


@pytest.fixture(scope="module")
def scenarios(tmp_path_factory, counted_http_block):
    return {
        scenario: run(tmp_path_factory.mktemp("b2"), scenario)
        for scenario in ("CR02-R03", "CR02-R02", "CR02-H03", prep.DEMO, "CR02-R04", "CR02-R05")
    }


def test_tool_projection_reproduces_b1_gap_without_losing_tool_body(tmp_path):
    prepared = prepare(tmp_path, "CR02-R03")
    adapter = MemoryAdapter("CR02-R03")
    with local_client(tmp_path, adapter) as (client, _):
        evidence = prep.run_case(client, prepared)
        review_id = evidence.data["phases"]["A"]["review_id"]
        original = ev.ReviewEvidence(client)
        original.capture(review_id)
        assert {g["code"] for g in original.data["gaps"]} == {"REQUEST_BODY_MISSING"}
        assert evidence.data["collection_complete"], evidence.data["gaps"]
        tools = [
            e
            for e in evidence.data["events"].values()
            if e["event_type"] == "request_projected" and e["payload"]["role"] == "tool"
        ]
        assert tools and all(e["payload"]["payload"]["tool"] == "read_source" for e in tools)
        assert all(e["event_id"] in evidence.data["request_projections"] for e in tools)


def test_r03_reuses_confirmed_rule_without_reapproval(scenarios):
    evidence, adapter, frozen, _ = scenarios["CR02-R03"]
    assert set(evidence.data["phases"]) == {"A", "B"}
    assert len(evidence.data["publications"]) == 1
    assert len({s["review_id"] for s in evidence.data["phases"].values()}) == 2
    identifiers = []
    for phase in ("A", "B"):
        state = evidence.data["phases"][phase]
        assert state["adopted_ruleset_version"] == 1
        assert state["status"] == "completed"
        records = project_adoptions(frozen[state["current_input_revision_id"]])
        assert {r["origin"]["project_decision_id"] for r in records} == {
            evidence.data["publications"]["allow"]["project_decision_id"]
        }
        assert all(r["input_revision_id"] == state["current_input_revision_id"] for r in records)
        identifiers.extend(r["adoption_id"] for r in records)
        report = phase_report(evidence, phase)["payload"]
        assert not report["questions"]
        assert {f["judgment_status"] for f in report["findings"]} == {"no_deviation"}
    assert len(identifiers) == len(set(identifiers))
    assert len(adapter.requests) == 8


def test_r02_reports_mutually_exclusive_rules_before_answer(scenarios):
    evidence, _, frozen, _ = scenarios["CR02-R02"]
    state = evidence.data["phases"]["A0"]
    assert state["status"] == "awaiting_decision"
    records = project_adoptions(frozen[state["current_input_revision_id"]])
    assert len(records) == 2
    assert (
        len(
            {
                (r["input_revision_id"], r["adopted_ruleset_version"], r["target_id"])
                for r in records
            }
        )
        == 1
    )
    assert all(r["disposition"] == "adopted" for r in records)
    assert len({json.dumps(r["declared_scope"], sort_keys=True) for r in records}) == 1
    assert {r["body"] for r in records} == {
        p["text"] for p in evidence.data["publications"].values()
    }
    report = phase_report(evidence, "A0")["payload"]
    assert {r["usage"] for r in report["rule_uses"]} == {"conflict"}
    assert {r["adoption_id"] for r in report["rule_uses"]} == {r["adoption_id"] for r in records}
    assert len(report["questions"]) == 1
    question = report["questions"][0]
    assert question["kind"] == "rule_conflict" and question["blocking"]
    assert set(question["rule_refs"]) == {r["adoption_id"] for r in records}
    assert {f["judgment_status"] for f in report["findings"]} == {"needs_decision"}
    assert not [m for m in evidence.data["mutations"] if "answers" in m["body"]]


def test_h03_local_answer_is_absent_from_review_b(scenarios):
    evidence, adapter, frozen, _ = scenarios["CR02-H03"]
    check_isolation(evidence, adapter, frozen)
    assert evidence.data["phases"]["B"]["status"] == "awaiting_decision"


def check_isolation(evidence, adapter, frozen):
    a0, a1, b = (evidence.data["phases"][p] for p in ("A0", "A1", "B"))
    assert a0["status"] == "awaiting_decision"
    assert a0["review_id"] == a1["review_id"] != b["review_id"]
    assert a0["current_input_revision_id"] != a1["current_input_revision_id"]
    answer = next(m for m in evidence.data["mutations"] if "answers" in m["body"])
    assert answer["status"] == 202
    text = answer["body"]["answers"][0]["text"]
    ids = answer["response"]["accepted_resolution_ids"]
    assert ids and set(ids) <= {r["id"] for r in evidence.data["test_store_resolutions"]}
    af = frozen[a1["current_input_revision_id"]]
    bf = frozen[b["current_input_revision_id"]]
    assert af["resolutions"][0]["answer"]["text"] == text
    assert bf["resolutions"] == []
    assert text not in json.dumps(bf, ensure_ascii=False)
    assert not any(identifier in json.dumps(bf) for identifier in ids)
    a_payloads, b_payloads = [], []
    for wire in adapter.requests:
        data = json.loads(wire["messages"][1]["content"])
        input_ids = {r["input_revision_id"] for r in data["adoption_records"]}
        if a1["current_input_revision_id"] in input_ids:
            a_payloads.append(data)
            assert data["resolutions"][0]["answer"]["text"] == text
        if b["current_input_revision_id"] in input_ids:
            b_payloads.append(data)
            assert data["resolutions"] == []
            assert text not in json.dumps(wire, ensure_ascii=False)
            assert not any(identifier in json.dumps(wire) for identifier in ids)
    assert a_payloads and b_payloads
    assert any("candidate_report" in d for d in a_payloads)
    assert any("candidate_report" in d for d in b_payloads)
    assert all(s["adopted_ruleset_version"] == 1 for s in (a0, a1, b))
    assert len(evidence.data["publications"]) == 1
    assert {r["disposition"] for r in project_adoptions(bf)} == {"excluded"}
    assert (
        phase_report(evidence, "A1")["payload"]["findings"][0]["judgment_status"]
        == "legitimate_version_difference"
    )
    assert evidence.data["semantic_verdict"] == "NOT_RUN"


def test_abc_demo_keeps_local_answer_and_formal_update_separate(scenarios):
    evidence, _, frozen, _ = scenarios[prep.DEMO]
    assert evidence.data["case_id"] is None and not evidence.data["aggregate_include"]
    assert set(evidence.data["phases"]) == {"A0", "A1", "B", "C"}
    for phase in ("A0", "A1", "B"):
        assert evidence.data["phases"][phase]["adopted_ruleset_version"] == 2
    assert evidence.data["phases"]["C"]["adopted_ruleset_version"] == 3
    assert phase_report(evidence, "B")["payload"]["questions"][0]["kind"] == "rule_conflict"
    c = phase_report(evidence, "C")["payload"]
    assert not c["questions"]
    assert {f["judgment_status"] for f in c["findings"]} == {"no_deviation"}
    cf = frozen[evidence.data["phases"]["C"]["current_input_revision_id"]]
    decisions = evidence.data["publications"]
    effective = [r for r in project_adoptions(cf) if r["disposition"] == "adopted"]
    assert {r["origin"]["project_decision_id"] for r in effective} == {
        decisions["allow"]["project_decision_id"]
    }
    removed = [
        r
        for r in project_adoptions(cf)
        if r["origin"]["project_decision_id"] == decisions["deny"]["project_decision_id"]
    ]
    assert removed and all(r["disposition"] == "excluded" for r in removed)
    assert all(r["body"] == decisions["deny"]["text"] for r in removed)
    assert not (
        {r["adoption_id"] for r in removed}
        & {r["adoption_id"] for r in c["rule_uses"] if r["usage"] in ("support", "conflict")}
    )
    mutations = evidence.data["mutations"]
    assert [m["body"].get("operation", "answer") for m in mutations] == [
        "confirm",
        "confirm",
        "answer",
        "withdraw",
    ]
    assert mutations[2]["status"] == 202
    assert frozen[evidence.data["phases"]["B"]["current_input_revision_id"]]["resolutions"] == []
    assert len(evidence.data["reports"]) == 4


def test_r04_replaces_only_cancel_and_preserves_old_view(scenarios):
    evidence, _, frozen, _ = scenarios["CR02-R04"]
    old, new = (evidence.data["phases"][p] for p in ("A_old", "B_new"))
    assert old["adopted_ruleset_version"] == 1 and new["adopted_ruleset_version"] == 2
    nf = frozen[new["current_input_revision_id"]]
    records = project_adoptions(nf)
    active = [r for r in records if r["disposition"] == "adopted"]
    assert {
        r["matched_target"]["endpoint"]["path"]: r["origin"]["project_decision_id"] for r in active
    } == {
        "/exports": evidence.data["publications"]["joint_old"]["project_decision_id"],
        "/exports/{job_id}/cancel": evidence.data["publications"]["cancel_new"][
            "project_decision_id"
        ],
    }
    removed = [r for r in records if r["reason_code"] == "SUPERSEDED_SLICE"]
    assert removed and all(
        r["body"] == evidence.data["publications"]["joint_old"]["text"] for r in removed
    )
    report = phase_report(evidence, "B_new")["payload"]
    assert not report["questions"] and not any(
        r["usage"] == "conflict" for r in report["rule_uses"]
    )
    assert [f["judgment_status"] for f in report["findings"]] == [
        "no_deviation",
        "supported_deviation",
    ]
    assert {
        f["judgment_status"] for f in phase_report(evidence, "A_old")["payload"]["findings"]
    } == {"no_deviation"}
    assert len(evidence.data["reports"]) == 2
    assert all(v["complete"] for v in evidence.data["ruleset_views"].values())


def test_r05_withdrawal_leaves_cancel_unknown_and_create_effective(scenarios):
    evidence, _, frozen, prepared = scenarios["CR02-R05"]
    state = evidence.data["phases"]["B_new"]
    nf = frozen[state["current_input_revision_id"]]
    cancel = [t for t in nf["target_manifest"] if t["endpoint"]["path"].endswith("/cancel")][0]
    # All normative entrances: formal adoption, authority source and local answers.
    assert not [
        r
        for r in nf["adoption_records"]
        if r["target_id"] == cancel["target_id"] and r["disposition"] == "adopted"
    ]
    assert nf["resolutions"] == []
    assert all(
        b["scope"]["endpoints"] == [{"method": "POST", "path": "/exports"}]
        for b in nf["authority_bindings"]
    )
    assert set(prepared["material_fingerprints"]) == {"src/api.py", "contracts/create-only.json"}
    contract = json.loads(
        (Path(prepared["case_root"]) / "contracts/create-only.json").read_text("utf-8")
    )
    assert "/cancel" not in json.dumps(contract)
    report = phase_report(evidence, "B_new")["payload"]
    assert [f["judgment_status"] for f in report["findings"]] == [
        "no_deviation",
        "insufficient_evidence",
    ]
    assert state["status"] == "completed_degraded"
    assert evidence.data["evidence_status"] == "COMPLETE"
    assert len(evidence.data["publications"]) == 2


def test_each_input_adoption_matches_actual_delivered_payload(scenarios):
    for values in scenarios.values():
        check_delivery(*values)


def check_delivery(evidence, adapter, frozen, prepared):
    scripts = json.loads((REPO / prep.CANDIDATE / "human-scripts.json").read_text("utf-8"))
    scripted_answers = {script["answer"]["text"] for script in scripts["scripts"].values()}
    events = evidence.data["events"]
    model_events = [
        e
        for e in events.values()
        if e["event_type"] == "request_projected" and e["payload"]["role"] != "tool"
    ]
    persisted = {c["call_id"]: c for c in evidence.data["test_store_calls"]}
    assert len(model_events) == len(adapter.requests)
    # Physical calls are paired by counted dispatch order, confirmed by ledger call ID.
    calls = [c for c in evidence.data["test_store_calls"] if c["kind"] == "model"]
    assert len(calls) == len(adapter.requests)
    for call_index, (call, wire) in enumerate(zip(calls, adapter.requests, strict=True)):
        same = [e for e in model_events if e["call_id"] == call["call_id"]]
        assert len(same) == 1
        event = same[0]
        assert event["review_id"] == call["review_id"] and event["job_id"] == call["job_id"]
        assert event["input_revision_id"] == call["input_id"]
        # AC10.1: no fields in the delivered payload are ignored.
        assert event["payload"]["payload"] == call["projection"]["payload"] == wire
        assert persisted[event["call_id"]]["remote_outcome"] == "known"
        data = json.loads(wire["messages"][1]["content"])
        current = frozen[event["input_revision_id"]]
        # AC10.2: expected input comes from Store and sealed fixture, not the projection.
        assert data["adoption_records"] == current["adoption_records"]
        assert data["resolutions"] == current["resolutions"]
        for rule in current["adoption_records"]:
            if rule["origin"]["kind"] == "project_decision":
                assert rule["body"] == next(
                    p["text"]
                    for p in evidence.data["publications"].values()
                    if p.get("project_decision_id") == rule["origin"]["project_decision_id"]
                )
                if rule["disposition"] == "adopted":
                    assert any(
                        m.get("body") == rule["body"]
                        and m.get("adoption_id") == rule["adoption_id"]
                        for m in data["rule_materials"]
                    )
        output = adapter.outputs[call_index]
        decisive = "candidate_report" in data or output.get("action") == "submit_report"
        if decisive:
            observed = {
                ref["source_id"]: o["body"]["text"]
                for o in data["observations"]
                for ref in o["source_refs"]
            }
            assert len(observed) == len(prepared["material_fingerprints"])
            for item in data["source_catalog"]["items"]:
                expected = (Path(prepared["case_root"]) / item["path"]).read_text("utf-8")
                assert observed[item["source_id"]] == expected
        # AC10.3: business input has a closed set of keys and exact authorized facts.
        assert set(data) <= {
            "request",
            "targets",
            "check_manifest",
            "adoption_records",
            "rule_materials",
            "resolutions",
            "review_directives",
            "source_catalog",
            "available_tools",
            "observations",
            "omitted_observation_ids",
            "candidate_report",
            "candidate_report_hash",
            "cited_materials",
        }
        assert data["request"] == prepared["request"]["request"]
        assert data["targets"] == current["target_manifest"]
        assert data["check_manifest"] == current["check_manifest"]
        assert data["review_directives"] == current.get("review_directives", [])
        role = call["projection"]["role"]
        assert wire["messages"][0]["content"] == current["execution_profile"][role + "_prompt"]
        legal_texts = {r["answer"].get("text") for r in current["resolutions"]}
        for text in scripted_answers - legal_texts:
            assert text not in json.dumps(wire, ensure_ascii=False)
        assert not any(
            s in json.dumps(data)
            for s in ("oracles.json", "criterion_id", "expected_phase_outcomes", "human_script_key")
        )
        all_answers = [a for f in frozen.values() for a in f["resolutions"]]
        own = {a["resolution_id"] for a in current["resolutions"]}
        for answer in all_answers:
            if answer["resolution_id"] not in own:
                assert answer["answer"]["text"] not in json.dumps(data, ensure_ascii=False)
    assert all(e["event_id"] in evidence.data["request_projections"] for e in model_events)


def test_memory_preparation_is_side_effect_free_and_has_no_live_entry(tmp_path, monkeypatch):
    reads, original = [], os._Environ.__getitem__

    def guarded(environment, key):
        if key in {
            "SPECFLOW_LLM_API_KEY",
            "SPECFLOW_LLM_BASE_URL",
            "SPECFLOW_LLM_MODEL",
            "SPECFLOW_API_KEY",
        }:
            reads.append(key)
            pytest.fail("Preparation read credential configuration")
        return original(environment, key)

    monkeypatch.setattr(os._Environ, "__getitem__", guarded)
    monkeypatch.setattr(
        httpx.Client, "post", lambda *a, **k: pytest.fail("Preparation dispatched HTTP")
    )
    result = prepare(tmp_path, "CR02-R03")
    assert (
        result["status"] == "PREPARED_NOT_DISPATCHED"
        and result["business_model_http_attempts"] == 0
    )
    assert result["semantic_verdict"] == "NOT_RUN" and not result["trial_consumed"]
    assert reads == []
    assert prep.main(["--case", prep.DEMO, "--output", str(tmp_path / "cli")]) == 0
    with pytest.raises(SystemExit) as error:
        prep.main(["--case", "CR02-R03", "--output", str(tmp_path / "bad"), "--live"])
    assert error.value.code == 2
    with pytest.raises(prep.PreparationError, match="CASE_NOT_IN_B2"):
        prepare(tmp_path, "CR02-H01")
    with pytest.raises(prep.PreparationError, match="OUTPUT_MUST_BE_OUTSIDE_CHECKOUT"):
        prep.prepare_case(REPO, REPO / "forbidden-output", "CR02-R03")


@pytest.mark.parametrize("tamper", ["identity", "request", "profile", "source", "bytes"])
def test_prepared_mismatch_stops_before_any_api_mutation(tmp_path, monkeypatch, tamper):
    prepared = prepare(tmp_path, "CR02-R03")
    if tamper == "identity":
        prepared["source_identity"]["trial_id"] = "foreign-trial"
    elif tamper == "request":
        prepared["request"]["request"] = "changed request"
    elif tamper == "profile":
        prepared["profile_id"] = "live"
    elif tamper == "source":
        prepared["request"]["source"]["groups"] = []
    else:
        root = Path(prepared["case_root"])
        (root / "src/api.py").write_text("changed", "utf-8")
        prep.git(root, "add", ".")
        prep.git(root, "commit", "-qm", "Tampered test fixture")
        prepared["request"]["source"]["commit_sha"] = (
            prep.git(root, "rev-parse", "HEAD").decode().strip()
        )
    with local_client(tmp_path, MemoryAdapter("CR02-R03")) as (client, _):
        monkeypatch.setattr(
            client, "post", lambda *a, **k: pytest.fail("Mismatch reached mutation")
        )
        with pytest.raises(prep.PreparationError, match="PREPARED_"):
            prep.run_case(client, prepared)


@pytest.mark.parametrize(
    "tamper",
    ["live_profile", "memory_disabled", "delegate_enabled", "live_adapter", "external_client"],
)
def test_runtime_guard_rejects_every_non_b2_boundary(tmp_path, tamper):
    adapter = MemoryAdapter("CR02-R03")
    with local_client(tmp_path, adapter) as (client, domain):
        if tamper == "external_client":
            with pytest.raises(prep.PreparationError, match="IN_PROCESS"):
                prep.require_test_runtime(object())
            return
        profile = domain.profiles[prep.PROFILE]
        if tamper == "live_profile":
            profile["execution_mode"] = "live"
        elif tamper == "memory_disabled":
            profile["options"]["project_memory"] = False
        elif tamper == "delegate_enabled":
            profile["options"]["delegate"] = True
        else:
            adapter.execution_mode = "live"
        with pytest.raises(prep.PreparationError, match="CONTROLLED_B2"):
            prep.require_test_runtime(client)


def test_publication_cas_and_same_key_replay_preserve_version(tmp_path):
    prepared = prepare(tmp_path, "CR02-R03")
    with local_client(tmp_path, MemoryAdapter("CR02-R03")) as (client, _):
        evidence = prep.run_case(client, prepared)
        publication = evidence.data["mutations"][0]
        path = f"/api/v1/projects/{evidence.data['project_id']}/contract-decisions"

        def post(body, key):
            return client.post(path, json=body, headers={"Idempotency-Key": key})

        replay = post(publication["body"], publication["key"])
        assert replay.status_code == 201 and replay.json() == publication["response"]
        assert (
            post({**publication["body"], "text": "different"}, publication["key"]).status_code
            == 409
        )
        assert post(publication["body"], "stale-cas").status_code == 409
        foreign = {
            "operation": "withdraw",
            "expected_ruleset_version": 1,
            "reason": "foreign ownership",
            "provenance": publication["body"]["provenance"],
            "withdrawals": [
                {
                    "project_decision_id": "foreign-decision",
                    "effective_scope": publication["body"]["scope"],
                }
            ],
        }
        assert post(foreign, "foreign").status_code == 404
        listed = client.get(path).json()
        assert listed["ruleset_version"] == 1 and len(listed["items"]) == 1
        valid = post({**publication["body"], "expected_ruleset_version": 1}, "next-independent")
        assert valid.status_code == 201
        assert client.get(path).json()["ruleset_version"] == 2


def test_answers_use_report_ids_and_auto_derived_job(tmp_path, monkeypatch):
    prepared = prepare(tmp_path, "CR02-H03")
    adapter = MemoryAdapter("CR02-H03")
    with local_client(tmp_path, adapter) as (client, domain):
        posts, original = [], client.post

        def post(path, **kwargs):
            posts.append((path, copy.deepcopy(kwargs.get("json"))))
            return original(path, **kwargs)

        monkeypatch.setattr(client, "post", post)
        evidence = prep.run_case(client, prepared)
        a0, a1, b = (evidence.data["phases"][p] for p in ("A0", "A1", "B"))
        mutation = next(m for m in evidence.data["mutations"] if "answers" in m["body"])
        assert mutation["body"]["expected_version"] == a0["version"]
        assert mutation["body"]["input_revision_id"] == a0["current_input_revision_id"]
        assert mutation["body"]["report_revision_id"] == a0["current_report_revision_id"]
        assert mutation["response"]["input_revision_id"] == a1["current_input_revision_id"]
        assert mutation["response"]["job_id"] == a1["job_id"] != a0["job_id"]
        replay = prep.submit_answers(
            evidence, a0["review_id"], mutation["body"]["answers"], mutation["key"]
        )
        assert replay["response"] == mutation["response"] and replay["status"] == 202
        assert (
            len(
                {
                    j
                    for j, info in evidence.data["jobs"].items()
                    if info["review_id"] == a0["review_id"]
                }
            )
            == 2
        )
        assert not any(path.endswith("/revisions") for path, _ in posts)
        before = len(posts)
        with pytest.raises(prep.PreparationError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
            prep.submit_answers(
                evidence,
                a0["review_id"],
                [{**mutation["body"]["answers"][0], "text": "changed"}],
                mutation["key"],
            )
        for answer in (
            {**mutation["body"]["answers"][0], "scope": "project"},
            {**mutation["body"]["answers"][0], "question_id": "foreign"},
        ):
            with pytest.raises(prep.PreparationError, match="ANSWER_NOT_ALLOWED"):
                prep.submit_answers(
                    evidence, b["review_id"], [answer], "invalid-" + uuid.uuid4().hex
                )
        assert len(posts) == before
        path = prep.API + "/" + b["review_id"] + "/resolution-batches"
        assert original(
            path, json=mutation["body"], headers={"Idempotency-Key": "foreign-input"}
        ).status_code in (404, 409)
        assert snapshot_input(domain, b["current_input_revision_id"])["resolutions"] == []


@pytest.mark.parametrize("variant", ["duplicate", "disallowed"])
def test_nonunique_or_disallowed_question_stops_without_answer(tmp_path, variant):
    prepared = prepare(tmp_path, "CR02-H03")
    with local_client(tmp_path, MemoryAdapter("CR02-H03", variant=variant)) as (client, _):
        evidence = prep.run_case(client, prepared)
        assert evidence.data["blocking"]["reason"] == "NO_UNIQUE_ALLOWED_QUESTION"
        assert evidence.data["workflow_verdict"] == "UNDETERMINED"
        assert not any("answers" in m["body"] for m in evidence.data["mutations"])
        assert set(evidence.data["phases"]) == {"A0"}
        assert (
            evidence.data["expected_slot_retained"]
            and evidence.data["semantic_verdict"] == "NOT_RUN"
        )


def test_partial_answer_waits_and_last_answer_derives_only_one_job(tmp_path):
    prepared = prepare(tmp_path, "CR02-H03")
    with local_client(tmp_path, MemoryAdapter("CR02-H03", variant="duplicate")) as (client, _):
        evidence = prep.run_case(client, prepared)
        state = evidence.data["phases"]["A0"]
        review_id = state["review_id"]
        report_id = state["current_report_revision_id"]
        questions = evidence.data["questions"][report_id]["items"]
        assert len(questions) == 2
        answers = [
            {
                "question_id": q["id"],
                "scope": "this_review",
                "answer_type": "clarify",
                "text": "本次测试答复：示例为v1。",
            }
            for q in questions
        ]
        first = prep.submit_answers(evidence, review_id, answers[:1], "partial-one")
        assert first["status"] == 200
        middle = evidence.capture(review_id)
        assert middle["status"] == "awaiting_decision"
        assert middle["current_input_revision_id"] == state["current_input_revision_id"]
        assert middle["job_id"] == state["job_id"]
        last = prep.submit_answers(evidence, review_id, answers[1:], "partial-last")
        assert last["status"] == 202
        final = evidence.capture(review_id)
        assert final["current_input_revision_id"] == last["response"]["input_revision_id"]
        assert final["job_id"] == last["response"]["job_id"] != state["job_id"]
        replay = prep.submit_answers(evidence, review_id, answers[1:], "partial-last")
        assert replay["response"] == last["response"]
        assert len(evidence.data["jobs"]) == 2


def test_clean_b_can_guess_wrong_without_being_classified_as_leakage(tmp_path):
    evidence, adapter, frozen, _ = run(tmp_path, "CR02-H03", variant="guess_v1")
    check_isolation(evidence, adapter, frozen)
    b = phase_report(evidence, "B")["payload"]
    assert b["findings"][0]["judgment_status"] == "legitimate_version_difference"
    assert not b["questions"]
    # This intentionally wrong controlled output violates the ambiguity oracle,
    # while the independently checked engineering isolation remains intact.
    assert evidence.data["semantic_verdict"] == "NOT_RUN"


def test_consistent_joint_omission_still_fails_completeness(scenarios):
    evidence, adapter, frozen, prepared = scenarios["CR02-R03"]
    damaged = SimpleNamespace(data=copy.deepcopy(evidence.data))
    delivered = SimpleNamespace(requests=copy.deepcopy(adapter.requests), outputs=adapter.outputs)
    wire = delivered.requests[-1]
    data = json.loads(wire["messages"][1]["content"])
    data["rule_materials"] = []
    wire["messages"][1]["content"] = json.dumps(data, ensure_ascii=False)
    calls = [c for c in damaged.data["test_store_calls"] if c["kind"] == "model"]
    call = calls[-1]
    call["projection"]["payload"] = wire
    event = next(
        e
        for e in damaged.data["events"].values()
        if e.get("call_id") == call["call_id"] and e["event_type"] == "request_projected"
    )
    event["payload"]["payload"] = wire
    assert event["payload"]["payload"] == wire
    with pytest.raises(AssertionError):
        check_delivery(damaged, delivered, frozen, prepared)


def test_history_gap_and_unknown_prevent_complete_verdict(tmp_path, monkeypatch):
    prepared = prepare(tmp_path, "CR02-R03")
    with local_client(tmp_path, MemoryAdapter("CR02-R03")) as (client, _):
        evidence = prep.run_case(client, prepared)
        review_id = evidence.data["phases"]["A"]["review_id"]
        original = client.get

        def missing(path, **kwargs):
            if "/events/" in path:
                return httpx.Response(404, json={"error": "missing historical payload"})
            return original(path, **kwargs)

        monkeypatch.setattr(client, "get", missing)
        evidence.capture(review_id)
        evidence.data["hard_failures"] = [{"error_code": "PRESERVED_FAILURE"}]
        prep.block(evidence, "EVIDENCE_INCOMPLETE", "historical-read")
        assert not evidence.data["collection_complete"] and evidence.data["gaps"]
        assert evidence.data["evidence_status"] == "INCOMPLETE"
        assert evidence.data["workflow_verdict"] == "FAIL"
        assert evidence.data["blocking"]["attempt_history"]
        assert set(evidence.data["phases"]) == {"A", "B"}
        if os.environ.get("B2_EVIDENCE_ROOT"):
            evidence.save(
                Path(os.environ["B2_EVIDENCE_ROOT"]) / ("HISTORY-GAP-" + uuid.uuid4().hex[:8])
            )

    class UnknownAdapter(MemoryAdapter):
        def complete(self, payload):
            self.requests.append(copy.deepcopy(payload))
            raise ProviderFailure("PROVIDER_TIMEOUT", remote_outcome="unknown")

    prepared = prepare(tmp_path, "CR02-R03")
    with local_client(tmp_path, UnknownAdapter("CR02-R03")) as (client, domain):
        evidence = prep.run_case(client, prepared)
        assert evidence.data["workflow_verdict"] == "FAIL"
        assert evidence.data["semantic_verdict"] == "NOT_RUN"
        assert evidence.data["expected_slot_retained"]
        with domain.store.read() as conn:
            calls = [
                json.loads(row[0])
                for row in conn.exec_driver_sql("SELECT body FROM contract_review_calls")
            ]
        assert calls and any(c["remote_outcome"] == "unknown" for c in calls)
        assert evidence.data["blocking"]["active"]
        if os.environ.get("B2_EVIDENCE_ROOT"):
            evidence.data["test_store_calls"] = calls
            evidence.save(
                Path(os.environ["B2_EVIDENCE_ROOT"]) / ("UNKNOWN-" + uuid.uuid4().hex[:8])
            )


def test_malformed_tool_and_model_bodies_are_not_exempted():
    evidence = prep.MemoryEvidence(object())
    evidence.data["evidence_status"] = "COMPLETE"
    for index, projection in enumerate(
        (
            {"role": "tool", "payload": {"tool": "read_source"}},
            {"role": "analysis", "payload": {"tool": "read_source", "arguments": {}}},
            {"role": "tool", "payload": {"tool": "read_source", "arguments": []}},
            {"role": "tool", "payload": {"tool": "read_source", "arguments": {}}},
            {"role": "tool", "payload": {"tool": "unknown_tool", "arguments": {}}},
        )
    ):
        event_id = "event" + str(index)
        evidence.data["events"][event_id] = {"event_id": event_id, "payload": projection}
        evidence.gap("REQUEST_BODY_MISSING", event_id=event_id)
    assert len(evidence.data["gaps"]) == 5
    assert not evidence.data["collection_complete"]
    assert evidence.data["evidence_status"] == "INCOMPLETE"
