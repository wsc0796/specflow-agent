import runpy
from pathlib import Path

line_contains_credential = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "check_secrets.py")
)["line_contains_credential"]


def test_secret_scan_covers_docs_and_non_allowlisted_tests() -> None:
    credential = "api_" + 'key="real-looking-credential-value"'
    assert line_contains_credential(credential, relative_path="docs/setup.md")
    assert line_contains_credential(credential, relative_path="tests/test_accidental_secret.py")


def test_secret_scan_allows_explicit_redaction_fixtures_only_in_tests() -> None:
    fixture = 'token="sk-abc123def456ghi789jkl012"'
    assert not line_contains_credential(fixture, relative_path="tests/test_redaction.py")
    assert line_contains_credential(fixture, relative_path="docs/example.md")
