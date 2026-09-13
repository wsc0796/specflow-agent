import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from specflow.api_security import ApiSecurity
from specflow.db import WorkflowRun
from specflow.main import create_app
from specflow.policy import RunStatus


@pytest.mark.parametrize(
    "terminal", ["success", "reject", "classified", "exception", "artifact", "evidence"]
)
def test_overlapping_api_requests_keep_audit_security_and_capacity(
    tmp_path,
    monkeypatch,
    caplog,
    terminal,
):
    from sqlalchemy import select

    import specflow.runner_multi as runner
    import specflow.runs as runs
    from specflow.policy import SpecFlowError
    from specflow.single_flight import Flight, SingleFlightCoordinator

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "feature.py").write_text("def feature(): return 1\n")
    coordinator = SingleFlightCoordinator()
    monkeypatch.setattr(runs, "DEFAULT_COORDINATOR", coordinator)
    entered, release, joined = Event(), Event(), Event()
    original_collect, original_wait = runner.EvidenceCollector.collect, Flight.wait
    calls = []

    def collect(self, **kwargs):
        calls.append("evidence")
        entered.set()
        assert release.wait(5)
        if terminal == "evidence":
            raise OSError("sensitive-api-failure-text")
        return original_collect(self, **kwargs)

    def wait(self, timeout):
        joined.set()
        return original_wait(self, timeout)

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    monkeypatch.setattr(Flight, "wait", wait)
    if terminal == "classified":

        def fail_budget(*args, **kwargs):
            raise SpecFlowError("CALL_BUDGET_EXCEEDED", "safe")

        monkeypatch.setattr(runner, "_run_and_accumulate", fail_budget)
    elif terminal == "reject":

        def reject(self, context):
            return {
                "agent_id": "review-agent-v1",
                "role": "review",
                "output": {
                    "decision": "REJECT",
                    "summary": "Business rejection.",
                    "target_agent_id": "design-agent-v1",
                },
            }

        monkeypatch.setattr(runner.ReviewAgent, "execute", reject)
    elif terminal == "exception":

        def fail_plan(*args, **kwargs):
            raise RuntimeError("sensitive-api-failure-text")

        monkeypatch.setattr(runner.Coordinator, "plan", fail_plan)
    elif terminal == "artifact":

        def fail_write(*args, **kwargs):
            raise OSError("sensitive-api-failure-text")

        monkeypatch.setattr(runner, "_safe_write", fail_write)
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        artifact_root=tmp_path / "run-artifacts",
        security=ApiSecurity(
            api_key=TEST_API_KEY,
            allowed_repository_roots=(str(repo),),
            max_runs_per_minute=2,
            max_concurrent_runs=1,
        ),
    )
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as client:
        project = register_project(client, repo)
        from specflow.db import Project

        with app.state.database.factory() as session:
            outside = Project(name="old-project", repository_path=str(tmp_path / "outside"))
            session.add(outside)
            session.commit()
            outside_id = outside.id
        payload = {"project_id": project, "requirement": "feature"}
        with ThreadPoolExecutor(2) as pool:
            owner = pool.submit(client.post, "/api/v1/runs", json=payload)
            try:
                assert entered.wait(5)
                assert (
                    client.post(
                        "/api/v1/runs", json=payload, headers={"X-API-Key": "wrong"}
                    ).status_code
                    == 401
                )
                assert (
                    client.post(
                        "/api/v1/runs", json={**payload, "project_id": outside_id}
                    ).status_code
                    == 403
                )
                # A different key is still denied; this rejection consumes no rate quota.
                assert (
                    client.post(
                        "/api/v1/runs", json={**payload, "requirement": "other"}
                    ).status_code
                    == 429
                )
                follower = pool.submit(client.post, "/api/v1/runs", json=payload)
                assert joined.wait(5)
                assert not owner.done() and not follower.done()
                assert calls == ["evidence"] and coordinator.active_count == 1
                assert client.post("/api/v1/runs", json=payload).status_code == 429
                with app.state.database.factory() as session:
                    rows = list(session.scalars(select(WorkflowRun)))
                    assert len(rows) == 2
                    assert {row.current_state for row in rows} == {"running"}
                    assert {row.state_payload["single_flight"]["role"] for row in rows} == {
                        "owner",
                        "follower",
                    }
            finally:
                release.set()
            responses = [owner.result(5), follower.result(5)]
        assert [response.status_code for response in responses] == [201, 201]
        first, second = [response.json() for response in responses]
        assert first["id"] != second["id"]
        assert first["single_flight"] == {"role": "owner", "owner_run_id": first["id"]}
        assert second["single_flight"] == {"role": "follower", "owner_run_id": first["id"]}
        expected_status = {"success": "completed", "reject": "rejected"}.get(
            terminal, "failed_runtime"
        )
        assert first["status"] == second["status"] == expected_status
        if terminal == "reject":
            assert first["error_code"] is None
        assert first["error_code"] == second["error_code"]
        if terminal == "classified":
            assert second["error_code"] == "CALL_BUDGET_EXCEEDED"
        if terminal == "success":
            assert first["artifact_available"] and second["artifact_available"]
            assert (
                client.get(f"/api/v1/runs/{first['id']}/artifacts").json()["files"]
                == (client.get(f"/api/v1/runs/{second['id']}/artifacts").json()["files"])
            )
        with app.state.database.factory() as session:
            first_row, second_row = [
                session.get(WorkflowRun, data["id"]) for data in (first, second)
            ]
            assert first_row.artifact_directory == second_row.artifact_directory
            assert second_row.state_payload["single_flight"] == second["single_flight"]
        assert not (tmp_path / "run-artifacts" / second["id"]).exists()
        assert coordinator.active_count == 0
        # Only the minute quota is exhausted: execution capacity was returned.
        permit = app.state.security._rate_limiter._semaphore.acquire(blocking=False)
        assert permit
        app.state.security._rate_limiter._semaphore.release()
    assert "sensitive-api-failure-text" not in caplog.text


TEST_API_KEY = "test-api-key"


@pytest.mark.parametrize("cancel_role", ["owner", "follower"])
def test_caller_cancellation_keeps_running_api_work_and_permit(tmp_path, monkeypatch, cancel_role):
    import asyncio

    import specflow.runner_multi as runner
    import specflow.runs as runs
    from specflow.single_flight import Flight, SingleFlightCoordinator

    coordinator = SingleFlightCoordinator()
    monkeypatch.setattr(runs, "DEFAULT_COORDINATOR", coordinator)
    entered, joined, release = Event(), Event(), Event()
    original_collect, original_wait = runner.EvidenceCollector.collect, Flight.wait
    calls = []

    def collect(self, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return original_collect(self, **kwargs)

    def wait(self, timeout):
        joined.set()
        return original_wait(self, timeout)

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    monkeypatch.setattr(Flight, "wait", wait)
    repo = tmp_path / "repo"
    repo.mkdir()
    with client_for(tmp_path) as client, ThreadPoolExecutor(2) as pool:
        project = register_project(client, repo)
        payload = {"project_id": project, "requirement": "feature"}
        raw_owner = pool.submit(client.post, "/api/v1/runs", json=payload)
        try:
            assert entered.wait(5)
            raw_follower = pool.submit(client.post, "/api/v1/runs", json=payload)
            assert joined.wait(5)

            async def abandon_wait():
                caller = asyncio.wrap_future(raw_owner if cancel_role == "owner" else raw_follower)
                caller.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await caller

            asyncio.run(abandon_wait())
            assert not raw_owner.done() and not raw_follower.done()
            assert coordinator.active_count == 1 and calls == [1]
            assert (
                client.post("/api/v1/runs", json={**payload, "requirement": "other"}).status_code
                == 429
            )
        finally:
            release.set()
        first, second = raw_owner.result(5).json(), raw_follower.result(5).json()
        assert first["status"] == second["status"] == "completed"
        assert coordinator.active_count == 0
        # The original execution actually finished before another owner enters.
        again = client.post("/api/v1/runs", json=payload)
        assert again.status_code == 201
        assert again.json()["single_flight"]["role"] == "owner"
        assert calls == [1, 1]


def test_api_follower_timeout_is_durable_and_does_not_release_owner(tmp_path, monkeypatch):
    import specflow.runner_multi as runner
    import specflow.runs as runs
    from specflow.single_flight import Flight, SingleFlightCoordinator

    coordinator = SingleFlightCoordinator()
    monkeypatch.setattr(runs, "DEFAULT_COORDINATOR", coordinator)
    entered, release = Event(), Event()
    original_collect, original_wait = runner.EvidenceCollector.collect, Flight.wait
    calls = []

    def collect(self, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return original_collect(self, **kwargs)

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    monkeypatch.setattr(Flight, "wait", lambda self, timeout: original_wait(self, 0))
    repo = tmp_path / "repo"
    repo.mkdir()
    with client_for(tmp_path) as client, ThreadPoolExecutor(1) as pool:
        project = register_project(client, repo)
        payload = {"project_id": project, "requirement": "feature"}
        owner = pool.submit(client.post, "/api/v1/runs", json=payload)
        try:
            assert entered.wait(5)
            timeout = client.post("/api/v1/runs", json=payload)
            assert timeout.status_code == 201
            body = timeout.json()
            assert body["status"] == "failed_runtime"
            assert body["error_code"] == "SINGLE_FLIGHT_WAIT_TIMEOUT"
            assert body["single_flight"]["role"] == "follower"
            assert not body["artifact_available"]
            assert coordinator.active_count == 1 and calls == [1]
            assert (
                client.post("/api/v1/runs", json={**payload, "requirement": "other"}).status_code
                == 429
            )
        finally:
            release.set()
        assert owner.result(5).json()["status"] == "completed"
        assert client.get(f"/api/v1/runs/{body['id']}").json()["error_code"] == (
            "SINGLE_FLIGHT_WAIT_TIMEOUT"
        )
    assert coordinator.active_count == 0


def test_api_cannot_share_direct_owner_artifacts_outside_its_root(tmp_path, monkeypatch):
    import specflow.runner_multi as runner
    import specflow.runs as runs
    from specflow.single_flight import Flight, SingleFlightCoordinator

    coordinator = SingleFlightCoordinator()
    monkeypatch.setattr(runs, "DEFAULT_COORDINATOR", coordinator)
    entered, joined, release = Event(), Event(), Event()
    original_collect, original_wait = runner.EvidenceCollector.collect, Flight.wait
    calls = []

    def collect(self, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return original_collect(self, **kwargs)

    def wait(self, timeout):
        joined.set()
        return original_wait(self, timeout)

    monkeypatch.setattr(runner.EvidenceCollector, "collect", collect)
    monkeypatch.setattr(Flight, "wait", wait)
    repo = tmp_path / "repo"
    repo.mkdir()
    with client_for(tmp_path) as client, ThreadPoolExecutor(2) as pool:
        project = register_project(client, repo)
        owner = pool.submit(
            runner.run_multi_agent,
            repo=repo,
            requirement="feature",
            output=tmp_path / "direct-output",
            mock=True,
            _coordinator=coordinator,
        )
        try:
            assert entered.wait(5)
            follower = pool.submit(
                client.post, "/api/v1/runs", json={"project_id": project, "requirement": "feature"}
            )
            assert joined.wait(5)
            assert calls == [1] and coordinator.active_count == 1
        finally:
            release.set()
        assert owner.result(5) == 0
        response = follower.result(5)
        assert response.status_code == 201
        body = response.json()
        assert body["single_flight"]["role"] == "follower"
        assert body["status"] == "failed_security"
        assert body["error_code"] == "SINGLE_FLIGHT_ARTIFACT_UNAVAILABLE"
        assert not body["artifact_available"]
        assert client.get(f"/api/v1/runs/{body['id']}/artifacts").status_code == 404
    assert coordinator.active_count == 0


def app_for(database_url: str, artifact_root: Path) -> FastAPI:
    return create_app(
        database_url,
        artifact_root=artifact_root,
        security=ApiSecurity(
            api_key=TEST_API_KEY,
            # Test repositories live under the same temp root as the artifacts.
            allowed_repository_roots=(str(artifact_root.parent.resolve()),),
        ),
    )


def client_for(tmp_path: Path) -> TestClient:
    return TestClient(
        app_for(
            f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            tmp_path / "run-artifacts",
        ),
        headers={"X-API-Key": TEST_API_KEY},
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
        raise RuntimeError("provider password=not-" + "for-api-output")

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


def test_run_api_exposes_runner_manifest_error_code(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    def fail_with_manifest(*, output: Path, **_: object) -> int:
        run_directory = output / "run-multi-failed"
        run_directory.mkdir(parents=True)
        (run_directory / "manifest.json").write_text(
            json.dumps({"error": "TIME_BUDGET_EXCEEDED"}), encoding="utf-8"
        )
        return 3

    monkeypatch.setattr("specflow.runs.run_multi_agent", fail_with_manifest)
    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )

    assert created.status_code == 201
    assert created.json()["error_code"] == "TIME_BUDGET_EXCEEDED"


def test_run_api_rejects_unsafe_runner_manifest_error(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    def fail_with_unsafe_manifest(*, output: Path, **_: object) -> int:
        run_directory = output / "run-multi-failed"
        run_directory.mkdir(parents=True)
        (run_directory / "manifest.json").write_text(
            json.dumps({"error": "provider password=not-" + "for-api-output"}), encoding="utf-8"
        )
        return 3

    monkeypatch.setattr("specflow.runs.run_multi_agent", fail_with_unsafe_manifest)
    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )

    assert created.status_code == 201
    assert created.json()["error_code"] == "RUNNER_FAILED"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation may require Windows privileges")
def test_run_api_does_not_read_a_symlinked_failed_manifest(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "manifest.json").write_text(
        json.dumps({"error": "EXTERNAL_ERROR_CODE"}), encoding="utf-8"
    )

    def fail_with_symlinked_manifest(*, output: Path, **_: object) -> int:
        output.mkdir(parents=True)
        (output / "run-multi-failed").symlink_to(outside, target_is_directory=True)
        return 3

    monkeypatch.setattr("specflow.runs.run_multi_agent", fail_with_symlinked_manifest)
    with client_for(tmp_path) as client:
        project_id = register_project(client, repository)
        created = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add a feature"},
        )

    assert created.status_code == 201
    assert created.json()["error_code"] == "RUNNER_FAILED"


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

    app = app_for(f"sqlite:///{database_path.as_posix()}", tmp_path / "artifacts")
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}):
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
    initial_app = app_for(database_url, artifacts)

    with TestClient(initial_app, headers={"X-API-Key": TEST_API_KEY}) as client:
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
    restarted_app = app_for(database_url, artifacts)
    with TestClient(restarted_app, headers={"X-API-Key": TEST_API_KEY}) as client:
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

    second_restart = app_for(database_url, artifacts)
    with TestClient(second_restart, headers={"X-API-Key": TEST_API_KEY}):
        with next(second_restart.state.database.sessions()) as session:
            recovered = session.get(WorkflowRun, "interrupted-run")
            assert recovered is not None
            assert recovered.version == 8


def test_startup_leaves_non_running_runs_untouched(tmp_path: Path) -> None:
    database_path = tmp_path / "states.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    app = app_for(database_url, tmp_path / "artifacts")

    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as client:
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

    restarted_app = app_for(database_url, tmp_path / "artifacts")
    with TestClient(restarted_app, headers={"X-API-Key": TEST_API_KEY}):
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
