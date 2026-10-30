"""Isolated committed materials, databases and explicitly test-only profiles."""

import copy
import json
import os
import subprocess
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
