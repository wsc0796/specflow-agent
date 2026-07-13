import tomllib
from pathlib import Path

from specflow import __version__
from specflow.main import create_app

EXPECTED_RELEASE_CANDIDATE = "1.1.0"


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

    assert "v1.1.0" in readme
    assert "unreleased" in readme.lower()
    assert "v1.0.1" in readme
    assert "v1.1.0" in changelog
    assert "Unreleased" in changelog
    assert "v1.0.1" in changelog
    assert "v1.1.0" in handoff
    assert "v1.0.1" in handoff
