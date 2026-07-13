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
SKIPPED_PREFIXES = ("docs/", "tests/")
SKIPPED_FILES = {".env.example"}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=root, text=True)
    return [root / line for line in output.splitlines()]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[str] = []
    for path in tracked_files(root):
        relative = path.relative_to(root).as_posix()
        if relative.startswith(SKIPPED_PREFIXES) or relative in SKIPPED_FILES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            if "re.compile" in line or 'r"' in line or "r'" in line:
                continue
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(relative)
                break
    if findings:
        print("Potential credential pattern in: " + ", ".join(findings), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
