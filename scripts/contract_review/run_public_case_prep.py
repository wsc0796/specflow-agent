"""Prepare fixed public cases; exercise workflows only through an injected test runtime.

The CLI prepares files only. It never starts a server/provider or loads credentials.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import uuid
from pathlib import Path

from review_evidence import PreparationError, ReviewEvidence

BASELINE = "ef2c53af26f0a02f61b4e7c8fa07e1d767a17029"
PROFILE = "b1-offline-public-v2"
HUMAN_CASES = frozenset(("CR02-H01", "CR02-H02"))
BINDINGS = {
    "CR02-F02": (
        ("contracts/v2.json", "contract", "contract-v2.json"),
        ("src/api.py", "implementation", "api-correct.py"),
        ("docs/api.md", "documentation", "docs-job-id.md"),
        ("examples/client.py", "example", "example-job-id.py"),
    ),
    **{
        case: (
            ("contracts/v2.json", "contract", "contract-v2.json"),
            ("src/api.py", "implementation", "api-correct.py"),
            ("contracts/v1.json", "contract", "contract-v1.json"),
            ("examples/client.py", "example", "example-ambiguous.py"),
        )
        for case in HUMAN_CASES
    },
}
API = "/api/v1/contract-reviews"


def git(repository, *args):
    environment = {
        k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ
    }
    environment.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_NAME="B1 offline fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="B1 offline fixture",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
    )
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "--no-lazy-fetch",
            "-c",
            "protocol.allow=never",
            "-c",
            "core.autocrlf=false",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(repository),
            *args,
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if result.returncode:
        raise PreparationError("FIXED_GIT_SOURCE_UNAVAILABLE")
    return result.stdout


def load_case(repository, case_id, *, trial_id=None, sample_id=None):
    if case_id not in BINDINGS:
        raise PreparationError("CASE_NOT_IN_B1")
    cases = json.loads(git(repository, "show", f"{BASELINE}:benchmarks/contract_review/cases.json"))
    selected = [case for case in cases if case["case_id"] == case_id]
    if len(selected) != 1:
        raise PreparationError("CASE_IDENTITY_MISMATCH")
    case = selected[0]
    expected_trial = "TR02-" + case_id.removeprefix("CR02-") + "-COMMON-01"
    expected_sample = expected_trial.replace("TR02-", "SP02-", 1)
    if (
        case["trial_id"] != expected_trial
        or case["sample_id"] != expected_sample
        or trial_id not in (None, expected_trial)
        or sample_id not in (None, expected_sample)
        or tuple((s["path"], s["role"], s["fixture"]) for s in case["sources"]) != BINDINGS[case_id]
    ):
        raise PreparationError("CASE_IDENTITY_MISMATCH")
    return case


def prepare_case(repository, output, case_id, *, trial_id=None, sample_id=None):
    repository, output = Path(repository).resolve(), Path(output).resolve()
    if output.is_relative_to(repository):
        raise PreparationError("OUTPUT_MUST_BE_OUTSIDE_CHECKOUT")
    case = load_case(repository, case_id, trial_id=trial_id, sample_id=sample_id)
    output.mkdir(parents=True, exist_ok=False)
    root = output / "case-repo"
    root.mkdir()
    for source in case["sources"]:
        path = root / source["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            git(
                repository,
                "show",
                f"{BASELINE}:benchmarks/contract_review/materials/{source['fixture']}",
            )
        )
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Original public case for B1 offline workflow")
    request = copy.deepcopy(case["request"])
    request["source"] = {
        "kind": "git_commit",
        "commit_sha": git(root, "rev-parse", "HEAD").decode().strip(),
        "groups": [{"role": s["role"], "paths": [s["path"]]} for s in case["sources"]],
    }
    prepared = {
        "schema_version": "cr02-b1-preparation.v1",
        "case_id": case_id,
        "source_trial_id": case["trial_id"],
        "sample_id": case["sample_id"],
        "fixture_source_commit": BASELINE,
        "execution_id": "b1-offline-" + uuid.uuid4().hex,
        "case_root": str(root),
        "request": request,
        "profile_id": PROFILE,
        "status": "PREPARED_NOT_DISPATCHED",
        "semantic_verdict": "NOT_RUN",
        "business_model_http_attempts": 0,
        "trial_consumed": False,
    }
    with (output / "preparation.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(prepared, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return prepared


def require_test_runtime(client):
    # Import only when explicitly exercising the local test workflow, never on CLI preparation.
    from starlette.testclient import TestClient

    if not isinstance(client, TestClient):
        raise PreparationError("IN_PROCESS_TEST_CLIENT_REQUIRED")
    domain = getattr(client.app.state, "contract_reviews", None)
    profile = domain.profiles.get(PROFILE) if domain else None
    worker = getattr(domain, "worker", None)
    if (
        not profile
        or profile["execution_mode"] != "test"
        or any(profile["options"].values())
        or worker is None
        or getattr(worker.adapter, "execution_mode", None) != "test"
    ):
        raise PreparationError("CONTROLLED_B1_RUNTIME_REQUIRED")


def submit_answers(evidence, review_id, answers, key):
    """Post once or replay the same recorded request; the host owns all successor creation."""
    require_test_runtime(evidence.client)
    previous = next((m for m in evidence.data["mutations"] if m["key"] == key), None)
    if previous is not None:
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
        f"{API}/{review_id}/resolution-batches",
        json=body,
        headers={"Idempotency-Key": key},
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
        return record
    evidence.capture(review_id)
    if response.status_code == 202:
        evidence.wait(review_id)
    return record


def run_case(client, prepared, *, repository=None, answer_human=True):
    """Exercise a fixed case using an already running, injected in-process test runtime."""
    require_test_runtime(client)
    repository = Path(repository or Path(__file__).resolve().parents[2])
    case = load_case(
        repository,
        prepared["case_id"],
        trial_id=prepared["source_trial_id"],
        sample_id=prepared["sample_id"],
    )
    submitted = copy.deepcopy(prepared["request"])
    if (
        {k: v for k, v in submitted.items() if k != "source"} != case["request"]
        or prepared["fixture_source_commit"] != BASELINE
        or prepared["profile_id"] != PROFILE
    ):
        raise PreparationError("PREPARED_CASE_MISMATCH")
    # Verify sealed case bytes and exact source grants before any review can be submitted.
    expected_groups = [{"role": s["role"], "paths": [s["path"]]} for s in case["sources"]]
    source = submitted["source"]
    if source.get("kind") != "git_commit" or source.get("groups") != expected_groups:
        raise PreparationError("PREPARED_SOURCE_MISMATCH")
    for s in case["sources"]:
        actual = git(prepared["case_root"], "show", f"{source['commit_sha']}:{s['path']}")
        expected = git(
            repository, "show", f"{BASELINE}:benchmarks/contract_review/materials/{s['fixture']}"
        )
        if actual != expected:
            raise PreparationError("PREPARED_SOURCE_MISMATCH")
    project = client.post(
        "/api/v1/projects",
        json={
            "name": prepared["case_id"] + " offline B1",
            "repository_path": prepared["case_root"],
        },
    )
    project.raise_for_status()
    submitted.update(project_id=project.json()["id"], execution_profile_id=PROFILE)
    response = client.post(
        API, json=submitted, headers={"Idempotency-Key": prepared["execution_id"]}
    )
    response.raise_for_status()
    accepted = response.json()
    evidence = ReviewEvidence(client)
    evidence.data.update(
        case_id=prepared["case_id"],
        source_trial_id=prepared["source_trial_id"],
        sample_id=prepared["sample_id"],
        execution_id=prepared["execution_id"],
        trial_consumed=False,
        accepted=accepted,
        submitted_request=submitted,
    )
    review_id = accepted["review_id"]
    state = evidence.wait(review_id)
    if (
        state is None
        or not evidence.data["collection_complete"]
        or not answer_human
        or prepared["case_id"] not in HUMAN_CASES
        or state["status"] != "awaiting_decision"
    ):
        return evidence
    report_id = state["current_report_revision_id"]
    items = evidence.data["questions"][report_id]["items"]
    target_ids = {c["target_id"] for c in state["check_manifest"]}
    candidates = [
        q
        for q in items
        if q["kind"] == "scope_choice"
        and q["blocking"]
        and q["answer_status"] == "unanswered"
        and set(q["target_ids"]) == target_ids
        and "clarify" in q["allowed_answer_types"]
    ]
    if len(candidates) != 1:
        evidence.data["human_stop_reason"] = "NO_UNIQUE_ALLOWED_SCOPE_QUESTION"
        return evidence
    # Load the original answer only AFTER a matching formal question exists.
    scripts = json.loads(
        git(repository, "show", f"{BASELINE}:benchmarks/contract_review/human-scripts.json")
    )
    answer = {**scripts["answers"][prepared["case_id"]], "question_id": candidates[0]["id"]}
    submit_answers(evidence, review_id, [answer], prepared["execution_id"] + ":answer")
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=sorted(BINDINGS))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare_case(Path(__file__).resolve().parents[2], args.output, args.case)
    except (PreparationError, OSError) as error:
        print(json.dumps({"status": "NOT_PREPARED", "error": str(error)}, ensure_ascii=False))
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
