import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from specflow.db import WorkflowRun
from specflow.main import create_app
from specflow.policy import RunStatus


def client_for(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            artifact_root=tmp_path / "run-artifacts",
        )
    )


def register_project(client: TestClient, repository_path: Path) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Fixture repository", "repository_path": repository_path.as_posix()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_get_and_list_mock_run_artifacts(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# Fixture repository\n", encoding="utf-8")

    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add an order search endpoint"},
        )

        assert created.status_code == 201
        body = created.json()
        assert body["project_id"] == project_id
        assert body["mode"] == "multi-agent"
        assert body["status"] == "completed"
        assert body["result_status"] == "completed"
        assert len(body["requirement_hash"]) == 64
        assert len(body["policy_hash"]) == 64
        assert body["artifact_available"] is True
        assert "artifact_directory" not in body
        assert repository.resolve().as_posix() not in json.dumps(body)

        fetched = client.get(f"/api/v1/runs/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == body["id"]

        artifacts = client.get(f"/api/v1/runs/{body['id']}/artifacts")
        assert artifacts.status_code == 200
        assert artifacts.json()["run_id"] == body["id"]
        assert "manifest.json" in artifacts.json()["files"]
        assert all("/" not in name and "\\" not in name for name in artifacts.json()["files"])


def test_run_api_rejects_invalid_resources_and_non_mock_execution(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        assert (
            client.post(
                "/api/v1/runs",
                json={"project_id": "missing", "requirement": "Add a feature"},
            ).status_code
            == 404
        )
        assert client.get("/api/v1/runs/missing").status_code == 404
        assert client.get("/api/v1/runs/missing/artifacts").status_code == 404

        repository = tmp_path / "repository"
        repository.mkdir()
        project_id = register_project(client, repository)
        assert (
            client.post(
                "/api/v1/runs",
                json={"project_id": project_id, "requirement": "Add a feature", "mock": False},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/runs",
                json={"project_id": project_id, "requirement": "   "},
            ).status_code
            == 422
        )


def test_missing_repository_is_a_persisted_safe_failure(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        project_id = register_project(client, tmp_path / "missing-repository")
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )

        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "failed_security"
        assert body["result_status"] == "failed_security"
        assert body["error_code"] == "REPOSITORY_UNAVAILABLE"
        assert "last_error" not in body
        assert client.get(f"/api/v1/runs/{body['id']}/artifacts").status_code == 404


def test_runner_exception_is_a_persisted_safe_runtime_failure(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    def raise_runner_error(**_: object) -> int:
        raise RuntimeError("provider password=not-for-api-output")

    monkeypatch.setattr("specflow.runs.run_multi_agent", raise_runner_error)
    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )

        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "failed_runtime"
        assert body["error_code"] == "RUNNER_FAILED"
        assert body["artifact_available"] is False
        assert "not-for-api-output" not in json.dumps(body)


def test_empty_artifact_directory_is_not_exposed_as_a_valid_artifact_index(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# Fixture repository\n", encoding="utf-8")

    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["artifact_available"] is True

        artifact_directory = next((tmp_path / "run-artifacts" / body["id"]).iterdir())
        for path in artifact_directory.iterdir():
            path.unlink()

        assert client.get(f"/api/v1/runs/{body['id']}/artifacts").status_code == 404
        assert (
            client.post(
                f"/api/v1/runs/{body['id']}/review-decisions",
                json={
                    "decision": "accepted",
                    "reviewer_label": "Reviewer",
                    "rationale": "Artifacts must exist before a decision is recorded.",
                },
            ).status_code
            == 409
        )


def test_completed_run_exposes_review_package_and_append_only_decisions(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# Fixture repository\n", encoding="utf-8")

    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add an order search endpoint"},
        )
        run_id = created.json()["id"]
        artifact_directory = next((tmp_path / "run-artifacts" / run_id).iterdir())
        for index in range(40):
            (artifact_directory / f"z-evidence-{index:02d}.txt").write_text(
                "bounded", encoding="utf-8"
            )

        package = client.get(f"/api/v1/runs/{run_id}/review-package")
        assert package.status_code == 200
        assert package.json()["run"]["id"] == run_id
        assert package.json()["run"]["status"] == RunStatus.COMPLETED
        assert package.json()["decisions"] == []
        assert "manifest.json" in package.json()["artifact_files"]
        assert len(package.json()["artifact_files"]) == 32
        assert repository.resolve().as_posix() not in json.dumps(package.json())

        accepted = client.post(
            f"/api/v1/runs/{run_id}/review-decisions",
            json={
                "decision": "accepted",
                "reviewer_label": "Engineering lead",
                "rationale": "Evidence and test plan are sufficient for implementation.",
            },
        )
        assert accepted.status_code == 201
        assert accepted.json()["decision"] == "accepted"

        needs_changes = client.post(
            f"/api/v1/runs/{run_id}/review-decisions",
            json={
                "decision": "needs_changes",
                "reviewer_label": "Engineering lead",
                "rationale": "Clarify rollback behavior before approval.",
            },
        )
        assert needs_changes.status_code == 201

        updated_package = client.get(f"/api/v1/runs/{run_id}/review-package")
        decisions = updated_package.json()["decisions"]
        assert [decision["decision"] for decision in decisions] == ["accepted", "needs_changes"]
        assert [decision["id"] for decision in decisions] == sorted(
            decision["id"] for decision in decisions
        )
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == RunStatus.COMPLETED


def test_review_decision_rejects_unknown_nonreviewable_and_invalid_runs(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        assert client.get("/api/v1/runs/missing/review-package").status_code == 404
        assert (
            client.post(
                "/api/v1/runs/missing/review-decisions",
                json={
                    "decision": "accepted",
                    "reviewer_label": "Reviewer",
                    "rationale": "Missing run should not be decided.",
                },
            ).status_code
            == 404
        )

        repository = tmp_path / "repository"
        repository.mkdir()
        project_id = register_project(client, repository)
        with next(client.app.state.database.sessions()) as session:
            session.add(
                WorkflowRun(
                    id="created-for-review",
                    project_id=project_id,
                    workflow_type="multi-agent",
                    current_state=RunStatus.CREATED,
                )
            )
            session.commit()

        assert client.get("/api/v1/runs/created-for-review/review-package").status_code == 409
        assert (
            client.post(
                "/api/v1/runs/created-for-review/review-decisions",
                json={
                    "decision": "accepted",
                    "reviewer_label": "Reviewer",
                    "rationale": "This run has no completed review package.",
                },
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/runs/created-for-review/review-decisions",
                json={
                    "decision": "rejected",
                    "reviewer_label": "Reviewer",
                    "rationale": "Unsupported decision.",
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/runs/created-for-review/review-decisions",
                json={
                    "decision": "accepted",
                    "reviewer_label": "x" * 101,
                    "rationale": "Reviewer labels are bounded.",
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/runs/created-for-review/review-decisions",
                json={
                    "decision": "accepted",
                    "reviewer_label": "Reviewer",
                    "rationale": " ",
                },
            ).status_code
            == 422
        )


def test_completed_degraded_run_remains_reviewable(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# Fixture repository\n", encoding="utf-8")

    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )
        run_id = created.json()["id"]
        with next(client.app.state.database.sessions()) as session:
            run = session.get(WorkflowRun, run_id)
            assert run is not None
            run.current_state = RunStatus.COMPLETED_DEGRADED
            run.result_status = RunStatus.COMPLETED_DEGRADED
            session.commit()

        assert client.get(f"/api/v1/runs/{run_id}/review-package").status_code == 200
        decision = client.post(
            f"/api/v1/runs/{run_id}/review-decisions",
            json={
                "decision": "needs_changes",
                "reviewer_label": "Reviewer",
                "rationale": "The degraded output requires a follow-up before implementation.",
            },
        )
        assert decision.status_code == 201
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == RunStatus.COMPLETED_DEGRADED


def test_startup_adds_run_metadata_to_a_legacy_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE workflow_runs (
                id VARCHAR(36) PRIMARY KEY,
                project_id VARCHAR(36) NOT NULL,
                requirement_id VARCHAR(36),
                workflow_type VARCHAR(64) NOT NULL,
                current_state VARCHAR(64),
                state_payload JSON,
                version INTEGER,
                result_status VARCHAR(32),
                paused_at DATETIME,
                started_at DATETIME,
                finished_at DATETIME,
                updated_at DATETIME,
                last_error TEXT
            )
            """
        )

    app = create_app(f"sqlite:///{database_path.as_posix()}", artifact_root=tmp_path / "artifacts")
    with TestClient(app):
        columns = {
            column["name"]
            for column in inspect(app.state.database.engine).get_columns("workflow_runs")
        }

    assert {
        "requirement_hash",
        "repository_alias",
        "policy_hash",
        "artifact_directory",
        "error_code",
    } <= columns
    assert "review_decisions" in inspect(app.state.database.engine).get_table_names()


def test_startup_recovers_interrupted_running_run_once(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "restart.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    artifacts = tmp_path / "artifacts"
    initial_app = create_app(database_url, artifact_root=artifacts)

    with TestClient(initial_app) as client:
        project_id = register_project(client, tmp_path / "repository")
        with next(initial_app.state.database.sessions()) as session:
            session.add(
                WorkflowRun(
                    id="interrupted-run",
                    project_id=project_id,
                    workflow_type="multi-agent",
                    current_state=RunStatus.RUNNING,
                    version=7,
                )
            )
            session.commit()

    def fail_if_runner_called(**_: object) -> int:
        raise AssertionError("startup recovery must not execute the runner")

    monkeypatch.setattr("specflow.runs.run_multi_agent", fail_if_runner_called)
    restarted_app = create_app(database_url, artifact_root=artifacts)
    with TestClient(restarted_app) as client:
        response = client.get("/api/v1/runs/interrupted-run")
        assert response.status_code == 200
        body = response.json()
        assert body["finished_at"] is not None
        assert body["status"] == RunStatus.FAILED_RUNTIME
        assert body["result_status"] == RunStatus.FAILED_RUNTIME
        assert body["error_code"] == "INTERRUPTED"
        with next(restarted_app.state.database.sessions()) as session:
            recovered = session.get(WorkflowRun, "interrupted-run")
            assert recovered is not None
            assert recovered.version == 8

    second_restart = create_app(database_url, artifact_root=artifacts)
    with TestClient(second_restart):
        with next(second_restart.state.database.sessions()) as session:
            recovered = session.get(WorkflowRun, "interrupted-run")
            assert recovered is not None
            assert recovered.version == 8


def test_startup_leaves_non_running_runs_untouched(tmp_path: Path) -> None:
    database_path = tmp_path / "states.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    app = create_app(database_url, artifact_root=tmp_path / "artifacts")

    with TestClient(app) as client:
        project_id = register_project(client, tmp_path / "repository")
        states = [
            RunStatus.CREATED,
            RunStatus.COMPLETED,
            RunStatus.COMPLETED_DEGRADED,
            RunStatus.REJECTED,
            RunStatus.FAILED_RUNTIME,
            RunStatus.FAILED_SECURITY,
            RunStatus.BUDGET_EXCEEDED,
            RunStatus.CANCELLED,
        ]
        with next(app.state.database.sessions()) as session:
            session.add_all(
                [
                    WorkflowRun(
                        id=f"non-running-{index}",
                        project_id=project_id,
                        workflow_type="multi-agent",
                        current_state=run_status,
                        result_status=None if run_status == RunStatus.CREATED else run_status,
                        error_code=(
                            "REPOSITORY_UNAVAILABLE"
                            if run_status == RunStatus.FAILED_SECURITY
                            else None
                        ),
                        version=index + 3,
                    )
                    for index, run_status in enumerate(states)
                ]
            )
            session.commit()

    restarted_app = create_app(database_url, artifact_root=tmp_path / "artifacts")
    with TestClient(restarted_app):
        with next(restarted_app.state.database.sessions()) as session:
            for index, run_status in enumerate(states):
                preserved = session.get(WorkflowRun, f"non-running-{index}")
                assert preserved is not None
                assert preserved.current_state == run_status
                assert preserved.result_status == (
                    None if run_status == RunStatus.CREATED else run_status
                )
                assert preserved.error_code == (
                    "REPOSITORY_UNAVAILABLE" if run_status == RunStatus.FAILED_SECURITY else None
                )
                assert preserved.version == index + 3
