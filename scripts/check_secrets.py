"""Fail CI when a tracked text file contains a likely committed credential."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(
        r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*['\"](?!<|example|test)[^'\"]{12,}['\"]"
    ),
)
SKIPPED_FILES = {".env.example", "scripts/check_secrets.py"}
TEST_FIXTURE_MARKERS = (
    "sk-abc",
    "sk-proj-abc",
    "sk-test-",
    '"api_key=" not in',
    "PROMPT_SECRET_MARKER",
    "SUBPROCESS_SECRET_MARKER",
)


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=root, text=True)
    return [root / line for line in output.splitlines()]


def line_contains_credential(line: str, *, relative_path: str) -> bool:
    """Detect a credential unless it is an explicit test-only redaction fixture."""
    if relative_path.startswith("tests/") and any(
        marker in line for marker in TEST_FIXTURE_MARKERS
    ):
        return False
    return any(pattern.search(line) for pattern in PATTERNS)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[str] = []
    for path in tracked_files(root):
        relative = path.relative_to(root).as_posix()
        if relative in SKIPPED_FILES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            if line_contains_credential(line, relative_path=relative):
                findings.append(relative)
                break
    if findings:
        print("Potential credential pattern in: " + ", ".join(findings), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
