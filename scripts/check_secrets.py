"""Fail CI when a tracked text file contains a likely committed credential."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Standalone prefix patterns: GitHub fine-grained tokens (ghp_), OpenAI-style
# keys (sk-), and AWS access key IDs (AKIA + 16 chars).
PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Quoted KEY=value assignments, e.g. token = "s3cret-value-1234567890".
    # The value charset excludes whitespace so assertion strings like
    # assert "api_key=" not in ... are not reported.
    re.compile(
        r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*['\"](?!<|example|test)"
        r"[^'\s\"]{12,}['\"]"
    ),
    # Unquoted KEY=value assignments, e.g. api_key=s3cret-value-1234567890.
    # The value charset excludes Python syntax (parentheses/brackets/quotes) so
    # ordinary code like `token = match.group()` is not reported, and at least
    # one non-letter character is required so plain identifiers such as
    # `token = authorization` are not treated as secrets.
    re.compile(
        r"(?i)\b(api[_-]?key|password|secret|token)\s*=\s*(?!<|example|test|redacted)"
        r"(?=[A-Za-z0-9_/+=:@-]*[0-9_/+=:@-])[A-Za-z0-9_/+=:@-]{12,}"
    ),
)
# Only these files are excluded. The scanner script itself is skipped because
# its own regex-definition lines are the pattern sources; every other file —
# including docs/ and tests/ — is scanned, so a fake credential planted in a
# test case is still reported.
SKIPPED_FILES = {".env.example", "scripts/check_secrets.py"}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=root, text=True)
    return [root / line for line in output.splitlines()]


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
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(relative)
                break
    if findings:
        print("Potential credential pattern in: " + ", ".join(findings), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
