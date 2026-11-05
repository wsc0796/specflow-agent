"""Isolated committed materials, databases and explicitly test-only profiles."""

import copy
import json
import os
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity
from specflow.db import Project
from specflow.main import create_app

MATERIAL_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "contract_review"
TEST_PROFILE = {
    "profile_id": "controlled-test-v1",
    "execution_mode": "test",
    "model": "controlled-test",
    "action_protocol": "contract-review-action.v2.1",
    "report_protocol": "contract-review-report-payload.v2.1",
    "support_matrix_version": "contract-static-support.v1",
    "completion_reserve": {"enabled": False},
    "mandatory_context_preflight": {"enabled": False},
    "options": {"write": False, "project_memory": False, "delegate": False, "replay": False},
}


@pytest.fixture
def test_profile():
    return copy.deepcopy(TEST_PROFILE)


@pytest.fixture
def git_repo(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_NAME="Fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="Fixture",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
    )

    def git(*args, data=None):
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "commit.gpgsign=false",
                "-C",
                str(root),
                *args,
            ],
            env=env,
            input=data,
            capture_output=True,
            timeout=10,
            check=True,
        )
        return result.stdout.decode("utf-8").strip()

    git("init", "-q")
    cases = json.loads((MATERIAL_ROOT / "cases.json").read_text(encoding="utf-8"))
    case = copy.deepcopy(next(item for item in cases if item["case_id"] == "CR02-F01"))
    for source in case["sources"]:
        path = root / source["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((MATERIAL_ROOT / "materials" / source["fixture"]).read_bytes())
    git("add", ".")
    git("commit", "-qm", "Frozen public fixture")
    request = case["request"]
    request.update(
        project_id="project-test",
        source={
            "kind": "git_commit",
            "commit_sha": git("rev-parse", "HEAD"),
            "groups": [{"role": item["role"], "paths": [item["path"]]} for item in case["sources"]],
        },
    )
    return root, git, request


@pytest.fixture
def review_client(tmp_path, git_repo):
    root, git, body = git_repo
    security = ApiSecurity(api_key="test-contract-key", allowed_repository_roots=(str(tmp_path),))
    app = create_app(
        f"sqlite:///{(tmp_path / 'reviews.sqlite').as_posix()}",
        tmp_path / "artifacts",
        security,
        contract_review_profiles={"controlled-test-v1": TEST_PROFILE},
    )
    with TestClient(app) as client:
        with app.state.database.factory() as session:
            session.add(
                Project(id="project-test", name="Public fixture", repository_path=str(root))
            )
            session.commit()
        client.headers["X-API-Key"] = "test-contract-key"
        yield client, app.state.contract_reviews, body


class ControlledAdapter:
    execution_mode = "test"

    def __init__(self, pauses=None, reject_review=False):
        self.requests = []
        self.pauses = pauses or {}
        self.entered = {index: threading.Event() for index in self.pauses}
        self.reject_review = reject_review
        self.before_response = None

    def complete(self, payload):
        self.requests.append(copy.deepcopy(payload))
        count = len(self.requests)
        if self.before_response:
            self.before_response(count)
        if count in self.pauses:
            self.entered[count].set()
            assert self.pauses[count].wait(8), "Test did not release the controlled call"
        data = json.loads(payload["messages"][1]["content"])
        if "candidate_report" in data:
            result = {
                "schema_version": "contract-review-review-result.v2",
                "type": "review_result",
                "candidate_report_hash": data["candidate_report_hash"],
                "outcome": "revise" if self.reject_review else "accept",
                "issues": (
                    [
                        {
                            "subject_kind": "report",
                            "subject_id": "",
                            "code": "other",
                            "reason": "受控返工场景",
                            "evidence_refs": [],
                        }
                    ]
                    if self.reject_review
                    else []
                ),
                "revision_feedback": "固定复核要求返工。" if self.reject_review else "",
            }
        else:
            missing = "受控替身仅验证程序链，不提供业务语义判断。"
            findings = [
                {
                    "id": "f" + str(index),
                    "target_ids": [target["target_id"]],
                    "judgment_status": "insufficient_evidence",
                    "affected_artifacts": ["documentation"],
                    "labels": [],
                    "claim": missing,
                    "rule_refs": [],
                    "source_refs": [],
                    "observation_refs": [],
                    "verification_evidence_refs": [],
                    "execution_verification": "NOT_RUN",
                    "limitations": [missing],
                }
                for index, target in enumerate(data["targets"])
            ]
            target_to_finding = {finding["target_ids"][0]: finding["id"] for finding in findings}
            report = {
                "schema_version": "contract-review-report-payload.v2.1",
                "summary": missing,
                "coverage": [
                    {
                        "target_id": target["target_id"],
                        "status": "partial",
                        "source_refs": [],
                        "missing_information": [missing],
                    }
                    for target in data["targets"]
                ],
                "check_results": [
                    {
                        "check_id": check["check_id"],
                        "status": "not_checked",
                        "finding_ids": [target_to_finding[check["target_id"]]],
                        "source_refs": [],
                        "observation_refs": [],
                        "missing_information": [missing],
                    }
                    for check in data["check_manifest"]
                ],
                "rule_uses": [],
                "findings": findings,
                "questions": [],
                "work_items": [],
                "acceptance_items": [],
                "adopted_child_result_refs": [],
                "limitations": [missing],
            }
            result = {
                "schema_version": "contract-review-action.v2.1",
                "action": "submit_report",
                "reason": {
                    "gap": "验证程序提交",
                    "evidence_refs": [],
                    "expected_information": "保存受控报告",
                },
                "report": report,
            }
        return {
            "content": json.dumps(result, ensure_ascii=False),
            "model": payload["model"],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }


@pytest.fixture
def running_app(tmp_path, git_repo, test_profile):
    root, _, request = git_repo

    @contextmanager
    def start(adapter, timeout=1.0):
        fast = {**test_profile, "model_timeout_seconds": timeout}
        slow = {**test_profile, "profile_id": "slow-test", "model_timeout_seconds": 5.0}
        app = create_app(
            f"sqlite:///{(tmp_path / 'worker.sqlite').as_posix()}",
            tmp_path / "artifacts",
            ApiSecurity(api_key="test-key", allowed_repository_roots=(str(tmp_path),)),
            contract_review_profiles={fast["profile_id"]: fast, slow["profile_id"]: slow},
            contract_review_adapter=adapter,
        )
        with TestClient(app) as client:
            with app.state.database.factory() as session:
                session.add(Project(id="project-test", name="Fixture", repository_path=str(root)))
                session.commit()
            client.headers["X-API-Key"] = "test-key"
            body = {**request, "execution_profile_id": fast["profile_id"]}
            try:
                yield client, app.state.contract_reviews, body
            finally:
                for event in adapter.pauses.values():
                    event.set()

    return start


@pytest.fixture
def controlled_adapter():
    return ControlledAdapter
