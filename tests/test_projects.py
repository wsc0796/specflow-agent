from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from specflow.db import Project, ProjectScan, WorkflowRun
from specflow.main import create_app


def client_for(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}"))


def test_create_and_get_project(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        created = client.post(
            "/api/v1/projects", json={"name": "Demo", "repository_path": "C:/demo"}
        )
        assert created.status_code == 201
        body = created.json()
        assert body["name"] == "Demo"
        assert body["status"] == "registered"
        fetched = client.get(f"/api/v1/projects/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["repository_path"] == "C:/demo"


def test_project_input_errors(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        assert (
            client.post(
                "/api/v1/projects", json={"name": "", "repository_path": "C:/x"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/projects", json={"name": "   ", "repository_path": "C:/x"}
            ).status_code
            == 422
        )
        payload = {"name": "Demo", "repository_path": "C:/demo"}
        assert client.post("/api/v1/projects", json=payload).status_code == 201
        assert client.post("/api/v1/projects", json=payload).status_code == 409
        assert (
            client.post(
                "/api/v1/projects", json={"name": "Demo", "repository_path": "   "}
            ).status_code
            == 422
        )
        assert client.get("/api/v1/projects/missing").status_code == 404


def test_core_persistence_tables_and_relationships(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    with TestClient(app):
        database = app.state.database
        assert {
            "projects",
            "project_scans",
            "workflow_runs",
        } <= set(inspect(database.engine).get_table_names())
        with next(database.sessions()) as session:
            project = Project(name="Demo", repository_path="C:/demo")
            session.add(project)
            session.flush()
            session.add(ProjectScan(project_id=project.id))
            session.add(WorkflowRun(project_id=project.id, workflow_type="analysis"))
            session.commit()
