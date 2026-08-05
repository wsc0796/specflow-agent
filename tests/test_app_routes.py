"""Route-structure regression tests for the module-level application."""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from specflow.api_security import ApiSecurity
from specflow.main import app, create_app

TEST_API_KEY = "test-api-key"


def _secured_app():
    return create_app(security=ApiSecurity(api_key=TEST_API_KEY))


def _health_routes(application) -> list[APIRoute]:
    return [
        route
        for route in application.routes
        if isinstance(route, APIRoute) and route.path == "/health"
    ]


def test_module_level_app_has_single_health_route() -> None:
    """The deployed app must expose exactly one /health route (T-062)."""
    routes = _health_routes(app)
    with TestClient(_secured_app(), headers={"X-API-Key": TEST_API_KEY}) as client:
        assert len(routes) == 1, f"expected one /health route, got {len(routes)}"
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_openapi_health_path_not_duplicated() -> None:
    with TestClient(_secured_app(), headers={"X-API-Key": TEST_API_KEY}) as client:
        spec = client.get("/openapi.json").json()
    health_operations = spec["paths"].get("/health")
    assert health_operations is not None, "/health missing from OpenAPI paths"
    assert len(health_operations) == 1, "OpenAPI declares /health more than once"
    assert health_operations["get"]["security"] == []
