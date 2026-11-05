"""Prepare B2 candidates; execute only with an injected in-process test runtime.

The CLI creates sealed, isolated Git materials only. It never loads credentials,
starts a provider, or treats controlled reports as model semantic validation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import uuid
from pathlib import Path

from review_evidence import PreparationError, ReviewEvidence
from run_public_case_prep import git

PROFILE = "b2-offline-memory-v2"
API = "/api/v1/contract-reviews"
CANDIDATE = Path("benchmarks/contract_review/candidates/b2-v0.3")
CASE_IDS = ("CR02-R02", "CR02-R03", "CR02-R04", "CR02-R05", "CR02-H03")
DEMO = "ABC-DEMO"
COMMON_MATERIALS = (
    (
        "contracts/create-only.json",
        "contract",
        str(CANDIDATE / "materials/contract-create-only.json"),
    ),
    ("src/api.py", "implementation", str(CANDIDATE / "materials/api-v2-static.py")),
)
H03_MATERIALS = (
    ("contracts/v2.json", "contract", "benchmarks/contract_review/materials/contract-v2.json"),
    ("src/api.py", "implementation", "benchmarks/contract_review/materials/api-correct.py"),
    ("contracts/v1.json", "contract", "benchmarks/contract_review/materials/contract-v1.json"),
    ("examples/client.py", "example", "benchmarks/contract_review/materials/example-ambiguous.py"),
)


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def load_case(repository, case_id):
    repository = Path(repository).resolve()
    if case_id not in (*CASE_IDS, DEMO):
        raise PreparationError("CASE_NOT_IN_B2")
    if case_id == DEMO:
        case = json.loads((repository / CANDIDATE / "demo-abc.json").read_text("utf-8"))
        if any(case[k] is not None for k in ("formal_case_id", "trial_id", "sample_id")):
            raise PreparationError("DEMO_HAS_FORMAL_IDENTITY")
    else:
        cases = json.loads((repository / CANDIDATE / "cases.json").read_text("utf-8"))["cases"]
        matches = [c for c in cases if c["identity"]["case_id"] == case_id]
        if len(matches) != 1:
            raise PreparationError("CASE_IDENTITY_MISMATCH")
        case = matches[0]
        suffix = case_id.removeprefix("CR02-")
        lane = "MEMORY" if suffix in ("R03", "R05") else "COMMON"
        identity = case["identity"]
        if (
            identity["trial_id"] != f"TR02-{suffix}-{lane}-01"
            or identity["sample_id"] != f"SP02-{suffix}-{lane}-01"
        ):
            raise PreparationError("CASE_IDENTITY_MISMATCH")
    expected = H03_MATERIALS if case_id == "CR02-H03" else COMMON_MATERIALS
    actual = tuple((m["path"], m["role"], str(Path(m["repo_fixture"]))) for m in case["materials"])
    if actual != tuple((p, r, str(Path(f))) for p, r, f in expected):
        raise PreparationError("MATERIAL_ALLOWLIST_MISMATCH")
    return case


def material_bytes(repository, material):
    root = Path(repository).resolve()
    path = root / material["repo_fixture"]
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise PreparationError("MATERIAL_OUTSIDE_CHECKOUT")
    return path.read_bytes()


def prepare_case(repository, output, case_id):
    repository, output = Path(repository).resolve(), Path(output).resolve()
    if output.is_relative_to(repository):
        raise PreparationError("OUTPUT_MUST_BE_OUTSIDE_CHECKOUT")
    case = load_case(repository, case_id)
    bodies = [(m, material_bytes(repository, m)) for m in case["materials"]]
    output.mkdir(parents=True, exist_ok=False)
    root = output / "case-repo"
    root.mkdir()
    for material, body in bodies:
        path = root / material["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Sealed B2 offline materials")
    request = copy.deepcopy(case["request_fields"])
    request["targets"] = [t["target"] for t in request["targets"]]
    request["source"] = {
        "kind": "git_commit",
        "commit_sha": git(root, "rev-parse", "HEAD").decode().strip(),
        "groups": [{"role": m["role"], "paths": [m["path"]]} for m in case["materials"]],
    }
    prepared = {
        "schema_version": "cr02-b2-preparation.v1",
        "case_id": case_id if case_id != DEMO else None,
        "scenario": case_id,
        "source_identity": case.get("identity"),
        "aggregate_include": case_id != DEMO,
        "candidate_version": "0.3",
        "candidate_fingerprint": fingerprint(case),
        "material_fingerprints": {
            m["path"]: hashlib.sha256(body).hexdigest() for m, body in bodies
        },
        "case_root": str(root),
        "request": request,
        "profile_id": PROFILE,
        "execution_id": "b2-offline-" + uuid.uuid4().hex,
        "status": "PREPARED_NOT_DISPATCHED",
        "semantic_verdict": "NOT_RUN",
        "oracle_status": "PENDING_INDEPENDENT_REVIEW",
        "business_model_http_attempts": 0,
        "trial_consumed": False,
    }
    (output / "preparation.json").write_text(
        json.dumps(prepared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return prepared


class MemoryEvidence(ReviewEvidence):
    """Extend B1's missing-body hook for genuine tool projections; keep all events.

    B1 inserts the raw event before calling gap(). A valid tool request has a
    tool/arguments body instead of messages. Malformed bodies still produce a
    gap; model projections and all other B1 integrity checks stay unchanged.
    """

    def gap(self, code, **context):
        if code == "REQUEST_BODY_MISSING":
            event = self.data["events"].get(context.get("event_id"), {})
            projection = event.get("payload", {})
            wire = projection.get("payload") if isinstance(projection, dict) else None
            if (
                isinstance(projection, dict)
                and projection.get("role") == "tool"
                and isinstance(wire, dict)
                and set(wire) == {"tool", "arguments"}
                and isinstance(wire["tool"], str)
                and wire["tool"]
                and isinstance(wire["arguments"], dict)
            ):
                from specflow.contract_review.tool_protocol import TOOL_ARGUMENTS

                model = TOOL_ARGUMENTS.get(wire["tool"])
                if model is not None:
                    try:
                        model.model_validate(wire["arguments"])
                    except ValueError:
                        pass
                    else:
                        self.data["request_projections"][event["event_id"]] = copy.deepcopy(
                            projection
                        )
                        return
        super().gap(code, **context)
        self.data["evidence_status"] = "INCOMPLETE"


def require_test_runtime(client):
    from starlette.testclient import TestClient

    if not isinstance(client, TestClient):
        raise PreparationError("IN_PROCESS_TEST_CLIENT_REQUIRED")
    domain = getattr(client.app.state, "contract_reviews", None)
    profile = domain.profiles.get(PROFILE) if domain else None
    worker = getattr(domain, "worker", None)
    if (
        not profile
        or profile["execution_mode"] != "test"
        or profile["engine_version"] != "contract-review-engine.v2"
        or profile["options"]
        != {"write": False, "project_memory": True, "delegate": False, "replay": False}
        or worker is None
        or getattr(worker.adapter, "execution_mode", None) != "test"
    ):
        raise PreparationError("CONTROLLED_B2_RUNTIME_REQUIRED")


def submit_answers(evidence, review_id, answers, key):
    require_test_runtime(evidence.client)
    previous = next((m for m in evidence.data["mutations"] if m["key"] == key), None)
    if previous:
        if previous["review_id"] != review_id or previous["body"]["answers"] != answers:
            raise PreparationError("IDEMPOTENCY_PAYLOAD_MISMATCH")
        body = copy.deepcopy(previous["body"])
    else:
        state = evidence.capture(review_id)
        if not state or not evidence.data["collection_complete"]:
            raise PreparationError("ANSWER_EVIDENCE_INCOMPLETE")
        if state["status"] != "awaiting_decision":
            raise PreparationError("NOT_AWAITING_DECISION")
        report_id = state["current_report_revision_id"]
        questions = {
            q["id"]: q
            for q in evidence.data["questions"][report_id]["items"]
            if q["answer_status"] == "unanswered"
        }
        if not answers or len({a["question_id"] for a in answers}) != len(answers):
            raise PreparationError("INVALID_ANSWER_BATCH")
        for answer in answers:
            question = questions.get(answer.get("question_id"))
            if (
                question is None
                or answer.get("scope") != "this_review"
                or answer.get("answer_type") not in question["allowed_answer_types"]
            ):
                raise PreparationError("ANSWER_NOT_ALLOWED")
        body = {
            "expected_version": state["version"],
            "input_revision_id": state["current_input_revision_id"],
            "report_revision_id": report_id,
            "answers": copy.deepcopy(answers),
        }
    response = evidence.client.post(
        f"{API}/{review_id}/resolution-batches", json=body, headers={"Idempotency-Key": key}
    )
    record = {
        "key": key,
        "review_id": review_id,
        "body": body,
        "status": response.status_code,
        "response": response.json(),
    }
    evidence.data["mutations"].append(copy.deepcopy(record))
    if response.status_code not in (200, 202):
        evidence.gap("ANSWER_REJECTED", status=response.status_code)
    elif response.status_code == 202:
        evidence.wait(review_id)
    else:
        evidence.capture(review_id)
    return record


def answer_current(evidence, review_id, case, script_key, repository, key):
    state = evidence.capture(review_id)
    if not state or not evidence.data["collection_complete"]:
        raise PreparationError("ANSWER_EVIDENCE_INCOMPLETE")
    # Only load a script once a current formal report actually exists.
    report_id = state.get("current_report_revision_id")
    if state["status"] != "awaiting_decision" or report_id not in evidence.data["questions"]:
        raise PreparationError("NO_CURRENT_FORMAL_QUESTION")
    scripts = json.loads((Path(repository) / CANDIDATE / "human-scripts.json").read_text("utf-8"))
    script = scripts["scripts"][script_key]
    match = script["question_match"]
    wanted = next(
        t["target"]
        for t in case["request_fields"]["targets"]
        if t["alias"] == match["target_alias"]
    )
    # Target IDs come from this input's actual projection, never from aliases.
    target_ids = set()
    for event_id, projection in evidence.data["request_projections"].items():
        if (
            evidence.data["events"][event_id]["input_revision_id"]
            != state["current_input_revision_id"]
        ):
            continue
        if projection["role"] == "tool":
            continue
        data = json.loads(projection["payload"]["messages"][1]["content"])
        for target in data["targets"]:
            if all(
                target.get(k) == wanted.get(k) for k in ("api_version", "endpoint", "source_path")
            ):
                target_ids.add(target["target_id"])
    questions = [
        q
        for q in evidence.data["questions"][report_id]["items"]
        if q["kind"] == match["kind"]
        and q["blocking"] == match["blocking"]
        and q["answer_status"] == "unanswered"
        and set(q["target_ids"]) == target_ids
        and match["required_answer_type"] in q["allowed_answer_types"]
    ]
    if len(target_ids) != 1 or len(questions) != 1:
        raise PreparationError("NO_UNIQUE_ALLOWED_QUESTION")
    answer = {**script["answer"], "question_id": questions[0]["id"]}
    return submit_answers(evidence, review_id, [answer], key)


def block(evidence, reason, phase):
    evidence.data["workflow_verdict"] = (
        "FAIL"
        if evidence.data.get("hard_failures") or evidence.data.get("workflow_verdict") == "FAIL"
        else "UNDETERMINED"
    )
    history = evidence.data.get("blocking", {}).get("attempt_history", [])
    evidence.data["blocking"] = {
        "active": True,
        "reason": reason,
        "phase": phase,
        "affected_case_or_demo": evidence.data["scenario"],
        "evidence_refs": list(evidence.data["reports"]),
        "local_defect_reference": reason,
        "resume_conditions": ["Resolve the recorded gap within separately authorized scope."],
        "attempt_history": [*history, {"reason": reason, "phase": phase}],
    }


def run_case(client, prepared, *, repository=None):
    require_test_runtime(client)
    repository = Path(repository or Path(__file__).resolve().parents[2])
    case = load_case(repository, prepared["scenario"])
    request = copy.deepcopy(prepared["request"])
    expected = copy.deepcopy(case["request_fields"])
    expected["targets"] = [t["target"] for t in expected["targets"]]
    groups = [{"role": m["role"], "paths": [m["path"]]} for m in case["materials"]]
    if (
        fingerprint(case) != prepared["candidate_fingerprint"]
        or prepared["profile_id"] != PROFILE
        or prepared["source_identity"] != case.get("identity")
        or prepared["aggregate_include"] != (prepared["scenario"] != DEMO)
        or prepared["case_id"] != (None if prepared["scenario"] == DEMO else prepared["scenario"])
        or {k: v for k, v in request.items() if k != "source"} != expected
        or request["source"].get("kind") != "git_commit"
        or request["source"].get("groups") != groups
    ):
        raise PreparationError("PREPARED_CASE_MISMATCH")
    for material in case["materials"]:
        actual = git(
            prepared["case_root"], "show", f"{request['source']['commit_sha']}:{material['path']}"
        )
        expected_body = material_bytes(repository, material)
        if (
            actual != expected_body
            or hashlib.sha256(actual).hexdigest()
            != prepared["material_fingerprints"][material["path"]]
        ):
            raise PreparationError("PREPARED_SOURCE_MISMATCH")
    project = client.post(
        "/api/v1/projects",
        json={
            "name": prepared["scenario"] + " offline B2",
            "repository_path": prepared["case_root"],
        },
    )
    project.raise_for_status()
    project_id = project.json()["id"]
    evidence = MemoryEvidence(client)
    evidence.data.update(
        scenario=prepared["scenario"],
        case_id=prepared["case_id"],
        source_identity=prepared["source_identity"],
        aggregate_include=prepared["aggregate_include"],
        execution_id=prepared["execution_id"],
        project_id=project_id,
        phases={},
        planned_phases=[
            step.get("save_as", step.get("save_successor_as")) for step in case["steps"]
        ],
        publications={},
        submitted_requests=[],
        semantic_verdict="NOT_RUN",
        workflow_verdict="NOT_RUN",
        business_model_http_attempts=0,
        trial_consumed=False,
        expected_slot_retained=True,
        blocking={"active": False},
    )
    prefix = prepared["execution_id"]
    for index, step in enumerate(case["steps"]):
        phase = step.get("save_as", step.get("save_successor_as"))
        if step["action"] in ("publish", "publish_effect"):
            body = copy.deepcopy(step["request_fields"])
            if "effect_binding" in step:
                binding = step["effect_binding"]
                alias = binding["project_decision_id_from"].split(".")[0]
                body[binding["field"]] = [
                    {
                        "project_decision_id": evidence.data["publications"][alias][
                            "project_decision_id"
                        ],
                        "effective_scope": binding["effective_scope"],
                    }
                ]
            response = client.post(
                f"/api/v1/projects/{project_id}/contract-decisions",
                json=body,
                headers={"Idempotency-Key": f"{prefix}:publish:{index}"},
            )
            evidence.data["mutations"].append(
                {
                    "key": f"{prefix}:publish:{index}",
                    "body": body,
                    "status": response.status_code,
                    "response": response.json(),
                }
            )
            if response.status_code != 201:
                evidence.data.setdefault("hard_failures", []).append(
                    {"phase": phase, "status": response.status_code, "response": response.json()}
                )
                evidence.gap("PUBLICATION_REJECTED", phase=phase, status=response.status_code)
                block(evidence, "PUBLICATION_REJECTED", phase)
                break
            evidence.data["publications"][phase] = response.json()
            evidence.ruleset(project_id, body["expected_ruleset_version"] + 1)
        elif step["action"] == "create_review_and_observe":
            submitted = {
                **request,
                "project_id": project_id,
                "execution_profile_id": PROFILE,
                "ruleset_usage": {
                    "mode": step["ruleset_usage_mode"],
                    "expected_ruleset_version": step["expected_ruleset_version"],
                },
            }
            response = client.post(
                API, json=submitted, headers={"Idempotency-Key": f"{prefix}:review:{index}"}
            )
            evidence.data["submitted_requests"].append(copy.deepcopy(submitted))
            if response.status_code != 202:
                evidence.data.setdefault("hard_failures", []).append(
                    {"phase": phase, "status": response.status_code, "response": response.json()}
                )
                evidence.gap("REVIEW_REJECTED", phase=phase, status=response.status_code)
                block(evidence, "REVIEW_REJECTED", phase)
                break
            state = evidence.wait(response.json()["review_id"])
            evidence.data["phases"][phase] = copy.deepcopy(state)
        else:
            parent = step["review_from"].split(".")[0]
            review_id = evidence.data["phases"][parent]["review_id"]
            try:
                result = answer_current(
                    evidence,
                    review_id,
                    case,
                    step["human_script_key"],
                    repository,
                    f"{prefix}:answer:{index}",
                )
            except PreparationError as error:
                block(evidence, str(error), phase)
                break
            if result["status"] != 202:
                block(evidence, "ANSWER_DID_NOT_DERIVE_SUCCESSOR", phase)
                break
            evidence.data["phases"][phase] = copy.deepcopy(evidence.capture(review_id))
        state = evidence.data["phases"].get(phase)
        if state and state["status"] not in (
            "completed",
            "completed_degraded",
            "awaiting_decision",
        ):
            evidence.data.setdefault("hard_failures", []).append(evidence.data["phases"][phase])
            block(evidence, "SERVICE_EXECUTION_FAILED", phase)
            break
        if not evidence.data["collection_complete"]:
            block(evidence, "EVIDENCE_INCOMPLETE", phase)
            break
    # Re-read every historical report/job and ruleset after all mutations.
    for review_id in {s["review_id"] for s in evidence.data["phases"].values() if s}:
        evidence.capture(review_id)
    for record in list(evidence.data["ruleset_views"].values()):
        evidence.ruleset(project_id, record["ruleset_version"])
    if not evidence.data["collection_complete"]:
        block(evidence, "EVIDENCE_INCOMPLETE", phase)
    evidence.data["evidence_status"] = (
        "COMPLETE" if evidence.data["collection_complete"] else "INCOMPLETE"
    )
    evidence.data["workflow_verdict"] = (
        evidence.data["workflow_verdict"] if evidence.data["blocking"]["active"] else "PASS"
    )
    evidence.data["service_observations"] = [
        {"phase": name, "state": copy.deepcopy(state)}
        for name, state in evidence.data["phases"].items()
    ]
    evidence.data["business_judgments"] = [
        {
            "phase": name,
            "report_revision_id": state["current_report_revision_id"],
            "findings": copy.deepcopy(
                evidence.data["reports"][state["current_report_revision_id"]]["json"]["payload"][
                    "findings"
                ]
            ),
        }
        for name, state in evidence.data["phases"].items()
        if state and state.get("current_report_revision_id") in evidence.data["reports"]
    ]
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=(*CASE_IDS, DEMO))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare_case(Path(__file__).resolve().parents[2], args.output, args.case)
    except (PreparationError, OSError, ValueError) as error:
        print(json.dumps({"status": "NOT_PREPARED", "error": str(error)}, ensure_ascii=False))
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
