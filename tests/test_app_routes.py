"""Route-structure regression tests for the module-level application."""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from specflow.main import app


def _health_routes() -> list[APIRoute]:
    return [
        route for route in app.routes if isinstance(route, APIRoute) and route.path == "/health"
    ]


def test_module_level_app_has_single_health_route() -> None:
    """The deployed app must expose exactly one /health route (T-062)."""
    with TestClient(app) as client:
        routes = _health_routes()
        assert len(routes) == 1, f"expected one /health route, got {len(routes)}"
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_openapi_health_path_not_duplicated() -> None:
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    health_operations = spec["paths"].get("/health")
    assert health_operations is not None, "/health missing from OpenAPI paths"
    assert len(health_operations) == 1, "OpenAPI declares /health more than once"
