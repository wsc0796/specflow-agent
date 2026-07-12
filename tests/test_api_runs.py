"""Tests for the SpecFlow API run management endpoints."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from specflow.main import app


@pytest.fixture(autouse=True)
def _set_dev_mode():
    old = os.environ.get("SPECFLOW_DEV_MODE")
    os.environ["SPECFLOW_DEV_MODE"] = "1"
    yield
    if old is None:
        os.environ.pop("SPECFLOW_DEV_MODE", None)
    else:
        os.environ["SPECFLOW_DEV_MODE"] = old


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    def test_health_responds(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_ready_responds(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestRunsAPI:
    def test_create_run(self, client, tmp_path: Path):
        resp = client.post(
            "/api/v1/runs",
            json={"repository_path": str(tmp_path), "requirement": "Add search endpoint"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "queued"

    def test_create_run_rejects_empty_requirement(self, client, tmp_path: Path):
        resp = client.post(
            "/api/v1/runs",
            json={"repository_path": str(tmp_path), "requirement": ""},
        )
        assert resp.status_code == 422

    def test_list_runs(self, client, tmp_path: Path):
        client.post("/api/v1/runs", json={"repository_path": str(tmp_path), "requirement": "X"})
        resp = client.get("/api/v1/runs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_run(self, client, tmp_path: Path):
        created = client.post(
            "/api/v1/runs", json={"repository_path": str(tmp_path), "requirement": "X"}
        )
        run_id = created.json()["run_id"]
        resp = client.get(f"/api/v1/runs/{run_id}")
        assert resp.status_code == 200

    def test_get_nonexistent_run(self, client):
        resp = client.get("/api/v1/runs/nonexistent")
        assert resp.status_code == 404

    def test_cancel_queued_run(self, client, tmp_path: Path):
        created = client.post(
            "/api/v1/runs", json={"repository_path": str(tmp_path), "requirement": "X"}
        )
        run_id = created.json()["run_id"]
        resp = client.post(f"/api/v1/runs/{run_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelling"
