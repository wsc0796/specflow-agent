"""Tests for fail-closed HTTP security: API key, allowlists, quotas, disposal."""

from pathlib import Path
from threading import Event, Thread

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from specflow.api_security import (
    DEFAULT_MAX_CONCURRENT_RUNS,
    DEFAULT_MAX_RUNS_PER_MINUTE,
    ApiSecurity,
    ApiSecurityConfigurationError,
    RunRateLimiter,
)
from specflow.main import create_app

FAKEKEY = "top-" + "secret-key"


def _client(tmp_path: Path, *, authenticated: bool = True, **security_kwargs) -> TestClient:
    configured_key = security_kwargs.setdefault("api_key", "test-api-key")
    security_kwargs.setdefault("allowed_repository_roots", (str(tmp_path),))
    return TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=ApiSecurity(**security_kwargs),
        ),
        headers={"X-API-Key": configured_key} if authenticated else None,
    )


def test_api_key_required_when_configured(tmp_path: Path) -> None:
    with _client(tmp_path, api_key=FAKEKEY, authenticated=False) as client:
        assert client.get("/api/v1/projects/nope").status_code == 401
        response = client.get("/api/v1/projects/nope", headers={"X-API-Key": FAKEKEY})
        assert response.status_code == 404  # authenticated, just not found
        response = client.get(
            "/api/v1/projects/nope", headers={"Authorization": f"Bearer {FAKEKEY}"}
        )
        assert response.status_code == 404
        wrong_key = client.get("/api/v1/projects/nope", headers={"X-API-Key": "wrong"})
        assert wrong_key.status_code == 401


def test_health_endpoint_stays_open_with_api_key(tmp_path: Path) -> None:
    with _client(tmp_path, api_key=FAKEKEY) as client:
        assert client.get("/health").status_code == 200


def test_startup_requires_non_empty_ascii_api_key(tmp_path: Path) -> None:
    for api_key in (None, "", "  ", "中文密钥"):
        app = create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=ApiSecurity(api_key=api_key),
        )
        with pytest.raises(ApiSecurityConfigurationError, match="SPECFLOW_API_KEY"):
            with TestClient(app):
                pass


def test_startup_requires_an_allowed_repository_root(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        security=ApiSecurity(api_key="test-api-key"),
    )
    with pytest.raises(ApiSecurityConfigurationError, match="SPECFLOW_ALLOWED_REPOSITORY_ROOTS"):
        with TestClient(app):
            pass


def test_validate_repository_path_rejects_every_path_without_allowlist() -> None:
    """Fail-closed: no allowlist means no repository path is accepted."""
    security = ApiSecurity(api_key="test-api-key")

    with pytest.raises(HTTPException) as error:
        security.validate_repository_path("C:/anything/at/all")
    assert error.value.status_code == 503


def test_documentation_and_openapi_routes_require_authentication(tmp_path: Path) -> None:
    with _client(tmp_path, authenticated=False) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 401

    with _client(tmp_path) as client:
        for path in ("/docs", "/redoc"):
            assert client.get(path).status_code == 200
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        security_schemes = schema.json()["components"]["securitySchemes"]
        assert security_schemes["ApiKeyAuth"]["name"] == "X-API-Key"
        assert security_schemes["BearerAuth"] == {"type": "http", "scheme": "bearer"}


def test_repository_path_allowlist(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    security = ApiSecurity(api_key="test-api-key", allowed_repository_roots=(str(allowed),))
    with TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=security,
        ),
        headers={"X-API-Key": "test-api-key"},
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

    with TestClient(
        create_app(
            database_url,
            artifact_root=tmp_path / "artifacts",
            security=ApiSecurity(
                api_key="test-api-key",
                allowed_repository_roots=(str(tmp_path),),
            ),
        ),
        headers={"X-API-Key": "test-api-key"},
    ) as client:
        project_id = client.post(
            "/api/v1/projects",
            json={"name": "Legacy", "repository_path": str(outside)},
        ).json()["id"]

    security = ApiSecurity(api_key="test-api-key", allowed_repository_roots=(str(allowed),))
    with TestClient(
        create_app(database_url, artifact_root=tmp_path / "artifacts", security=security),
        headers={"X-API-Key": "test-api-key"},
    ) as client:
        response = client.post(
            "/api/v1/runs", json={"project_id": project_id, "requirement": "Check"}
        )

    assert response.status_code == 403


def test_reviewer_label_allowlist(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# repo\n", encoding="utf-8")
    security = ApiSecurity(
        api_key="test-api-key",
        allowed_repository_roots=(str(repository),),
        reviewer_labels=frozenset({"engineering-lead"}),
    )
    with TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=security,
        ),
        headers={"X-API-Key": "test-api-key"},
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
    security = ApiSecurity(
        api_key="test-api-key",
        allowed_repository_roots=(str(repository),),
        max_runs_per_minute=2,
        max_concurrent_runs=1,
    )
    with TestClient(
        create_app(
            f"sqlite:///{(tmp_path / 'security.db').as_posix()}",
            artifact_root=tmp_path / "artifacts",
            security=security,
        ),
        headers={"X-API-Key": "test-api-key"},
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
        security=ApiSecurity(
            api_key="test-api-key",
            allowed_repository_roots=(str(tmp_path),),
        ),
    )
    with TestClient(app):
        assert disposed == []
    assert disposed == [True]


def test_oversized_ascii_api_key_rejects_without_500(tmp_path: Path) -> None:
    """Oversized credentials must be a clean 401, never a 500."""
    with _client(tmp_path, api_key=FAKEKEY, authenticated=False) as client:
        hostile = "x" * 10_000
        via_header = client.get("/api/v1/projects/nope", headers={"X-API-Key": hostile})
        assert via_header.status_code == 401
        via_bearer = client.get(
            "/api/v1/projects/nope", headers={"Authorization": f"Bearer {hostile}"}
        )
        assert via_bearer.status_code == 401


def test_require_api_key_rejects_non_ascii_input() -> None:
    """Non-ASCII provided keys must be a 401, never a TypeError (T-062).

    HTTP clients cannot carry non-ASCII headers, so this exercises the
    security layer directly — the path a non-ASCII configured key hits.
    """
    security = ApiSecurity(api_key=FAKEKEY)
    for hostile in ("中文密钥", "🚀✨emoji-key", "éclair-café", "​" * 3):
        with pytest.raises(HTTPException) as error:
            security.require_api_key(None, x_api_key=hostile, authorization=None)
        assert error.value.status_code == 401
        with pytest.raises(HTTPException) as error:
            security.require_api_key(None, x_api_key=None, authorization=f"Bearer {hostile}")
        assert error.value.status_code == 401


def test_require_api_key_non_ascii_configured_key_never_matches() -> None:
    """A non-ASCII configured key matches nothing (T-062)."""
    security = ApiSecurity(api_key="中文密钥")
    for attempted in ("中文密钥", "top-secret-key", "ascii-key"):
        with pytest.raises(HTTPException) as error:
            security.require_api_key(None, x_api_key=attempted)
        assert error.value.status_code == 401


@pytest.mark.parametrize(
    "authorization",
    ["Basic dG9wLXNlY3JldC1rZXk=", "Bearer", "Bearer  "],
)
def test_malformed_or_wrong_scheme_authorization_rejects(
    tmp_path: Path, authorization: str
) -> None:
    with _client(tmp_path, api_key=FAKEKEY, authenticated=False) as client:
        response = client.get("/api/v1/projects/nope", headers={"Authorization": authorization})
        assert response.status_code == 401


@pytest.mark.parametrize("header_value", ["", "   "])
def test_empty_api_key_header_rejects(tmp_path: Path, header_value: str) -> None:
    with _client(tmp_path, api_key=FAKEKEY, authenticated=False) as client:
        response = client.get("/api/v1/projects/nope", headers={"X-API-Key": header_value})
        assert response.status_code == 401


def test_default_quotas_match_documented_values() -> None:
    """Runtime quota constants must be the source for code and docs (T-062)."""
    security = ApiSecurity.from_env(environment={})
    direct_security = ApiSecurity()
    direct_limiter = RunRateLimiter()
    for limiter in (
        security._rate_limiter,
        direct_security._rate_limiter,
        direct_limiter,
    ):
        assert limiter._per_minute == DEFAULT_MAX_RUNS_PER_MINUTE
        assert limiter._max_concurrent == DEFAULT_MAX_CONCURRENT_RUNS

    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    env_example = (root / ".env.example").read_text(encoding="utf-8")
    assert f"Run-creation burst cap (default `{DEFAULT_MAX_RUNS_PER_MINUTE}`)." in readme
    assert f"Maximum simultaneous runs (default `{DEFAULT_MAX_CONCURRENT_RUNS}`)." in readme
    assert f"# SPECFLOW_MAX_RUNS_PER_MINUTE={DEFAULT_MAX_RUNS_PER_MINUTE}" in env_example
    assert f"# SPECFLOW_MAX_CONCURRENT_RUNS={DEFAULT_MAX_CONCURRENT_RUNS}" in env_example


def test_correct_key_works_on_both_headers(tmp_path: Path) -> None:
    with _client(tmp_path, api_key=FAKEKEY, authenticated=False) as client:
        via_header = client.get("/api/v1/projects/nope", headers={"X-API-Key": FAKEKEY})
        assert via_header.status_code == 404  # authenticated, just not found
        via_bearer = client.get(
            "/api/v1/projects/nope",
            headers={"Authorization": f"Bearer {FAKEKEY}"},
        )
        assert via_bearer.status_code == 404
        lowercase = client.get(
            "/api/v1/projects/nope",
            headers={"Authorization": "bearer top-secret-key"},
        )
        assert lowercase.status_code == 404  # RFC 7235: scheme is case-insensitive
