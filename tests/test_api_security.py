"""Tests for opt-in HTTP hardening: API key, path allowlist, quotas, disposal."""

from pathlib import Path
from threading import Event, Thread

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity, RunRateLimiter
from specflow.main import create_app


def _client(tmp_path: Path, **security_kwargs) -> TestClient:
    return TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=ApiSecurity(**security_kwargs),
        )
    )


def test_api_key_required_when_configured(tmp_path: Path) -> None:
    with _client(tmp_path, api_key="top-secret-key") as client:
        assert client.get("/api/v1/projects/nope").status_code == 401
        response = client.get("/api/v1/projects/nope", headers={"X-API-Key": "top-secret-key"})
        assert response.status_code == 404  # authenticated, just not found
        response = client.get(
            "/api/v1/projects/nope", headers={"Authorization": "Bearer top-secret-key"}
        )
        assert response.status_code == 404
        wrong_key = client.get("/api/v1/projects/nope", headers={"X-API-Key": "wrong"})
        assert wrong_key.status_code == 401


def test_health_endpoint_stays_open_with_api_key(tmp_path: Path) -> None:
    with _client(tmp_path, api_key="top-secret-key") as client:
        assert client.get("/health").status_code == 200


def test_repository_path_allowlist(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    security = ApiSecurity(allowed_repository_roots=(str(allowed),))
    with TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=security,
        )
    ) as client:
        outside = client.post(
            "/api/v1/projects",
            json={"name": "Outside", "repository_path": str(tmp_path / "outside")},
        )
        assert outside.status_code == 403
        inside = client.post(
            "/api/v1/projects",
            json={"name": "Inside", "repository_path": str(allowed / "repo")},
        )
        assert inside.status_code == 201


def test_repository_path_allowlist_is_rechecked_before_a_run(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "README.md").write_text("# repository\n", encoding="utf-8")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    database_url = f"sqlite:///{(tmp_path / 'security.db').as_posix()}"

    with TestClient(create_app(database_url, artifact_root=tmp_path / "artifacts")) as client:
        project_id = client.post(
            "/api/v1/projects",
            json={"name": "Legacy", "repository_path": str(outside)},
        ).json()["id"]

    security = ApiSecurity(allowed_repository_roots=(str(allowed),))
    with TestClient(
        create_app(database_url, artifact_root=tmp_path / "artifacts", security=security)
    ) as client:
        response = client.post(
            "/api/v1/runs", json={"project_id": project_id, "requirement": "Check"}
        )

    assert response.status_code == 403


def test_reviewer_label_allowlist(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# repo\n", encoding="utf-8")
    security = ApiSecurity(reviewer_labels=frozenset({"engineering-lead"}))
    with TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=security,
        )
    ) as client:
        project_id = client.post(
            "/api/v1/projects",
            json={"name": "Demo", "repository_path": str(repository)},
        ).json()["id"]
        run_id = client.post(
            "/api/v1/runs",
            json={"project_id": project_id, "requirement": "Add search"},
        ).json()["id"]
        rejected = client.post(
            f"/api/v1/runs/{run_id}/review-decisions",
            json={
                "decision": "accepted",
                "reviewer_label": "self-declared",
                "rationale": "Looks good",
            },
        )
        assert rejected.status_code == 403
        accepted = client.post(
            f"/api/v1/runs/{run_id}/review-decisions",
            json={
                "decision": "accepted",
                "reviewer_label": "engineering-lead",
                "rationale": "Looks good",
            },
        )
        assert accepted.status_code == 201


def test_run_rate_limiter_rejects_bursts() -> None:
    limiter = RunRateLimiter(per_minute=1, max_concurrent=1)
    permit = limiter.acquire()
    permit.release()
    with pytest.raises(HTTPException):
        limiter.acquire()


def test_concurrency_rejection_does_not_consume_run_rate_quota() -> None:
    limiter = RunRateLimiter(per_minute=2, max_concurrent=1)
    held_permit = limiter.acquire()
    with pytest.raises(HTTPException, match="already in progress"):
        limiter.acquire()
    held_permit.release()

    next_permit = limiter.acquire()
    next_permit.release()


def test_http_concurrency_rejection_does_not_consume_run_rate_quota(
    tmp_path: Path, monkeypatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    started = Event()
    release = Event()

    def slow_runner(**_: object) -> int:
        started.set()
        assert release.wait(timeout=3)
        return 0

    monkeypatch.setattr("specflow.runs.run_multi_agent", slow_runner)
    security = ApiSecurity(max_runs_per_minute=2, max_concurrent_runs=1)
    with TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=security,
        )
    ) as client:
        project_id = client.post(
            "/api/v1/projects",
            json={"name": "Demo", "repository_path": str(repository)},
        ).json()["id"]
        first_response: list[object] = []
        first = Thread(
            target=lambda: first_response.append(
                client.post(
                    "/api/v1/runs",
                    json={"project_id": project_id, "requirement": "First"},
                )
            )
        )
        first.start()
        assert started.wait(timeout=1)

        rejected = client.post(
            "/api/v1/runs", json={"project_id": project_id, "requirement": "Second"}
        )
        assert rejected.status_code == 429

        release.set()
        first.join(timeout=3)
        assert not first.is_alive()
        assert first_response[0].status_code == 201

        allowed = client.post(
            "/api/v1/runs", json={"project_id": project_id, "requirement": "Third"}
        )

    assert allowed.status_code == 201


def test_engine_is_disposed_on_shutdown(tmp_path: Path, monkeypatch) -> None:
    import specflow.main as main_module
    from specflow.db import Database

    expected_url = f"sqlite:///{(tmp_path / 'dispose.db').as_posix()}"
    database = Database(expected_url)
    disposed = []
    original = database.engine.dispose

    def spy_dispose() -> None:
        disposed.append(True)
        return original()

    database.engine.dispose = spy_dispose  # type: ignore[method-assign]

    def database_factory(url: str) -> Database:
        assert url == expected_url
        return database

    monkeypatch.setattr(main_module, "Database", database_factory)
    app = main_module.create_app(
        database_url=expected_url,
        artifact_root=tmp_path / "artifacts",
    )
    with TestClient(app):
        assert disposed == []
    assert disposed == [True]
