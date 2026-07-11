"""Deterministic, evidence-backed Python/FastAPI technology detection.

T-004.1: Integrated with RepositoryScanner — the detector no longer traverses
the filesystem independently.  It receives a ScanResult and reads only files
that passed T-003 safety checks (within allowed roots, not oversized, not in
ignored directories).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from specflow.scanner import ScanResult


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
    parse_warnings: list[str] = field(default_factory=list)


class SafeFileAccessor:
    """Read repository files only when they passed the T-003 safety scan.

    Enforces:
    - The path is inside the scanned root.
    - The file exists in the ScanResult (not in an ignored directory).
    - The file is not oversized.
    """

    def __init__(self, scan: ScanResult) -> None:
        self._root = Path(scan.root).resolve()
        self._allowed: set[str] = {
            f.path for f in scan.files if not f.is_oversized
        }

    @property
    def root(self) -> Path:
        return self._root

    def read_text(self, relative_path: str) -> str:
        """Read *relative_path* if it was included in the safety scan."""
        resolved = (self._root / relative_path).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            raise _AccessError(f"Path outside repository root: {relative_path}")
        if resolved.relative_to(self._root).as_posix() not in self._allowed:
            raise _AccessError(f"Not in safe scan result: {relative_path}")
        return resolved.read_text(encoding="utf-8", errors="ignore")

    def file_exists(self, relative_path: str) -> bool:
        resolved = (self._root / relative_path).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return False
        return resolved.relative_to(self._root).as_posix() in self._allowed

    def python_files(self) -> list[str]:
        """Return sorted list of *.py file paths visible in the safe scan result."""
        return sorted(p for p in self._allowed if p.endswith(".py"))


class _AccessError(Exception):
    """Raised when code attempts to read a file outside the safe scan boundary."""


class TechnologyStackDetector:
    """Recognize only supported facts explicitly present in repository files.

    After T-004.1 the detector MUST be given a ScanResult so it cannot
    accidentally crawl ignored / oversized / out-of-root files.
    """

    # ── public API ──────────────────────────────────────────────

    def detect(self, scan: ScanResult) -> TechnologyStack:
        """Build a TechnologyStack from a T-003 safety scan.

        If *scan* is empty (no files at all) the result is ``language=unknown``.
        """
        accessor = SafeFileAccessor(scan)
        evidence: list[Evidence] = []
        warnings: list[str] = []

        # ── dependency metadata ──
        dep_files: list[str] = []
        deps: list[tuple[str, str]] = []

        if accessor.file_exists("pyproject.toml"):
            dep_files.append("pyproject.toml")
            deps.extend(self._pyproject_deps(accessor, evidence, warnings))

        if accessor.file_exists("requirements.txt"):
            dep_files.append("requirements.txt")
            deps.extend(self._requirements_deps(accessor, evidence))

        # ── language detection ──
        has_python = bool(accessor.python_files()) or bool(dep_files)
        if has_python:
            evidence.append(Evidence("repository", "*.py or Python dependency metadata"))

        names = {name for name, _ in deps}

        # ── framework / tool identification (dependency-based only) ──
        frameworks = ["fastapi"] if "fastapi" in names else []
        orm = "sqlalchemy" if "sqlalchemy" in names else None
        validation_library = "pydantic" if "pydantic" in names else None
        test_framework = "pytest" if "pytest" in names else None
        lint_tools = ["ruff"] if "ruff" in names else []

        # ── database: confirmed from dependencies only ──
        database = "sqlite" if any(n in {"sqlite", "aiosqlite"} for n in names) else None

        # ── entry-point scanning (uses SafeFileAccessor, not raw rglob) ──
        entries = self._entry_candidates(accessor, evidence)

        return TechnologyStack(
            language="python" if has_python else "unknown",
            frameworks=frameworks,
            validation_library=validation_library,
            orm=orm,
            database=database,
            test_framework=test_framework,
            lint_tools=lint_tools,
            dependency_files=dep_files,
            application_entry_candidates=entries,
            evidence=evidence,
            parse_warnings=warnings,
        )

    # ── dependency parsing ─────────────────────────────────────

    # PEP 508 extras / version-specifier / environment-marker separators
    _EXTRAS_RE = re.compile(r"\[.*\]")
    _MARKER_RE = re.compile(r";.*$")
    _URL_RE = re.compile(r"@\s*\S+")
    _VERSION_OPS = re.compile(r"[~<>=!]")

    @classmethod
    def _normalized_name(cls, raw: str) -> str:
        """Extract the distribution name from a PEP 508 dependency string.

        Handles::

            fastapi==0.115        # ==
            pydantic>=2           # >=
            sqlalchemy<3          # <
            fastapi~=0.115        # ~= (T-004.1 fix)
            pytest!=8.0           # != (T-004.1 fix)
            package[extra]        # extras
            pkg; python>="3.12"   # environment markers (T-004.1 fix)
            pkg @ https://...     # direct URLs    (T-004.1 fix)
        """
        value = raw.strip()
        value = cls._EXTRAS_RE.sub("", value, count=1)
        value = cls._MARKER_RE.sub("", value, count=1)
        value = cls._URL_RE.sub("", value, count=1)
        # split on first version-operator character
        parts = cls._VERSION_OPS.split(value, maxsplit=1)
        return parts[0].strip().lower()

    # ── file readers (all go through SafeFileAccessor) ─────────

    @staticmethod
    def _pyproject_deps(
        accessor: SafeFileAccessor,
        evidence: list[Evidence],
        warnings: list[str],
    ) -> list[tuple[str, str]]:
        try:
            document = tomllib.loads(accessor.read_text("pyproject.toml"))
            project = document.get("project", {})
            deps = list(project.get("dependencies", []))
            for group in document.get("dependency-groups", {}).values():
                deps.extend(group)
            items: list[tuple[str, str]] = []
            for entry in deps:
                name = TechnologyStackDetector._normalized_name(entry)
                items.append((name, entry))
                evidence.append(Evidence("pyproject.toml", entry))
            return items
        except tomllib.TOMLDecodeError:
            warnings.append("pyproject.toml could not be parsed")
            return []

    @staticmethod
    def _requirements_deps(
        accessor: SafeFileAccessor,
        evidence: list[Evidence],
    ) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for line in accessor.read_text("requirements.txt").splitlines():
            entry = line.strip()
            if entry and not entry.startswith(("#", "-")):
                name = TechnologyStackDetector._normalized_name(entry)
                items.append((name, entry))
                evidence.append(Evidence("requirements.txt", entry))
        return items

    # ── entry-point scanning ────────────────────────────────────

    @staticmethod
    def _entry_candidates(
        accessor: SafeFileAccessor,
        evidence: list[Evidence],
    ) -> list[str]:
        candidates: list[str] = []
        for rel_path in accessor.python_files():
            content = accessor.read_text(rel_path)
            if "FastAPI(" in content:
                candidates.append(rel_path)
                evidence.append(Evidence(rel_path, "FastAPI("))
        return sorted(candidates)
