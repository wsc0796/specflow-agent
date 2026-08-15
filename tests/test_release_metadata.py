import importlib.util
import tomllib
import urllib.request
from pathlib import Path

from specflow import __version__
from specflow.main import create_app

EXPECTED_RELEASE_CANDIDATE = "1.1.1"


def _load_smoke_module():
    path = Path("scripts/smoke_installed_wheel.py")
    spec = importlib.util.spec_from_file_location("specflow_wheel_smoke", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_candidate_version_has_one_runtime_truth_source() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_version = project["project"]["version"]

    assert package_version == EXPECTED_RELEASE_CANDIDATE
    assert __version__ == package_version
    assert create_app().version == package_version
    assert create_app().openapi()["info"]["version"] == package_version


def test_current_release_documents_distinguish_candidate_from_published_tag() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    handoff = Path("docs/handoffs/CURRENT-STATE-2026-07-13.md").read_text(encoding="utf-8")

    assert "v1.1.1" in readme
    assert "unreleased" in readme.lower()
    assert "v1.0.1" in readme
    assert "v1.1.1" in changelog
    assert "Unreleased" in changelog
    assert "v1.0.1" in changelog
    assert "v1.1.1" in handoff
    assert "v1.0.1" in handoff


def test_installed_wheel_smoke_loopback_client_disables_ambient_proxies() -> None:
    smoke = _load_smoke_module()
    proxy_handlers = [
        handler
        for handler in smoke.LOOPBACK_OPENER.handlers
        if isinstance(handler, urllib.request.ProxyHandler)
    ]
    # ProxyHandler({}) contributes no proxy methods, so build_opener omits it
    # entirely; the dedicated opener therefore cannot consult ambient proxies.
    assert proxy_handlers == []


def test_installed_wheel_smoke_configures_temporary_repository_root(tmp_path: Path) -> None:
    smoke = _load_smoke_module()
    environment = smoke._server_environment(tmp_path)
    assert environment["SPECFLOW_API_KEY"] == smoke.SMOKE_CREDENTIAL
    assert environment["SPECFLOW_ALLOWED_REPOSITORY_ROOTS"] == str(tmp_path)
