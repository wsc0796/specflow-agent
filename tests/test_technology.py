from pathlib import Path

from specflow.technology import TechnologyStackDetector


def test_detects_supported_pyproject_stack_with_evidence(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\ndependencies = ['fastapi', 'pydantic>=2', 'sqlalchemy', 'aiosqlite']\n"
        "[dependency-groups]\ndev = ['pytest', 'ruff']\n"
    )
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    result = TechnologyStackDetector().detect(tmp_path)
    assert result.language == "python"
    assert result.frameworks == ["fastapi"]
    assert result.validation_library == "pydantic"
    assert result.orm == "sqlalchemy"
    assert result.database == "sqlite"
    assert result.test_framework == "pytest"
    assert result.lint_tools == ["ruff"]
    assert result.dependency_files == ["pyproject.toml"]
    assert result.application_entry_candidates == ["main.py"]
    assert any(item.matched == "fastapi" for item in result.evidence)


def test_detects_requirements_and_sqlite_entry_evidence(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("fastapi==1.0\npytest\nruff\n")
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\nurl = 'sqlite:///x.db'\n"
    )
    result = TechnologyStackDetector().detect(tmp_path)
    assert result.dependency_files == ["requirements.txt"]
    assert result.application_entry_candidates == ["app.py"]
    assert result.database == "sqlite"
    assert any(item.file == "app.py" and item.matched == "sqlite" for item in result.evidence)


def test_unknown_repository_is_not_guessed(tmp_path: Path) -> None:
    result = TechnologyStackDetector().detect(tmp_path)
    assert result.language == "unknown"
    assert result.frameworks == []
    assert result.evidence == []
