"""Deterministic, evidence-backed Python/FastAPI technology detection."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Evidence:
    file: str
    matched: str


@dataclass(frozen=True)
class TechnologyStack:
    language: str = "unknown"
    frameworks: list[str] = field(default_factory=list)
    validation_library: str | None = None
    orm: str | None = None
    database: str | None = None
    test_framework: str | None = None
    lint_tools: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    application_entry_candidates: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


class TechnologyStackDetector:
    """Recognize only supported facts explicitly present in repository files."""

    def detect(self, root: Path) -> TechnologyStack:
        root = root.resolve(strict=True)
        evidence: list[Evidence] = []
        dependency_files: list[str] = []
        dependencies: list[tuple[str, str]] = []

        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            dependency_files.append("pyproject.toml")
            dependencies.extend(self._pyproject_dependencies(pyproject, evidence))
        requirements = root / "requirements.txt"
        if requirements.is_file():
            dependency_files.append("requirements.txt")
            dependencies.extend(self._requirements_dependencies(requirements, evidence))

        has_python = any(root.rglob("*.py")) or bool(dependency_files)
        if has_python:
            evidence.append(Evidence("repository", "*.py or Python dependency metadata"))

        names = {name for name, _ in dependencies}
        frameworks = ["fastapi"] if "fastapi" in names else []
        orm = "sqlalchemy" if "sqlalchemy" in names else None
        validation_library = "pydantic" if "pydantic" in names else None
        test_framework = "pytest" if "pytest" in names else None
        lint_tools = ["ruff"] if "ruff" in names else []
        entries = self._entry_candidates(root, evidence)
        database = (
            "sqlite"
            if any(name in {"sqlite", "aiosqlite"} for name in names)
            or any(item.matched == "sqlite" for item in evidence)
            else None
        )

        return TechnologyStack(
            language="python" if has_python else "unknown",
            frameworks=frameworks,
            validation_library=validation_library,
            orm=orm,
            database=database,
            test_framework=test_framework,
            lint_tools=lint_tools,
            dependency_files=dependency_files,
            application_entry_candidates=entries,
            evidence=evidence,
        )

    @staticmethod
    def _normalized_name(value: str) -> str:
        return (
            value.lower()
            .split("[", 1)[0]
            .split("=", 1)[0]
            .split(">", 1)[0]
            .split("<", 1)[0]
            .strip()
        )

    def _pyproject_dependencies(
        self, path: Path, evidence: list[Evidence]
    ) -> list[tuple[str, str]]:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        project = document.get("project", {})
        values = list(project.get("dependencies", []))
        for group in document.get("dependency-groups", {}).values():
            values.extend(group)
        result = []
        for value in values:
            name = self._normalized_name(value)
            result.append((name, value))
            evidence.append(Evidence("pyproject.toml", value))
        return result

    def _requirements_dependencies(
        self, path: Path, evidence: list[Evidence]
    ) -> list[tuple[str, str]]:
        result = []
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith(("#", "-")):
                result.append((self._normalized_name(value), value))
                evidence.append(Evidence("requirements.txt", value))
        return result

    @staticmethod
    def _entry_candidates(root: Path, evidence: list[Evidence]) -> list[str]:
        candidates = []
        for path in root.rglob("*.py"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            if "FastAPI(" in content:
                relative = path.relative_to(root).as_posix()
                candidates.append(relative)
                evidence.append(Evidence(relative, "FastAPI("))
            if "sqlite" in content.lower():
                evidence.append(Evidence(path.relative_to(root).as_posix(), "sqlite"))
        return sorted(candidates)
