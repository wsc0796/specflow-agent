import tomllib
from pathlib import Path


def test_package_version_matches_current_release_documentation() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "1.0.1"
    assert "v1.0.1" in Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "v1.0.1" in Path("README.md").read_text(encoding="utf-8")
