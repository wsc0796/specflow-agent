"""Mock contract evaluation runner; it never selects a real provider."""

from __future__ import annotations

import json
from pathlib import Path

from specflow.evaluation.models import (
    EvaluationCase,
    EvaluationMode,
    EvaluationReport,
    EvaluationRun,
    EvaluationStatus,
    LiveValidationRecord,
)
from specflow.evaluation.validators import validate_artifacts
from specflow.runner import run


def load_cases(cases_root: Path) -> tuple[EvaluationCase, ...]:
    """Load sorted JSON case definitions without private absolute paths."""
    cases: list[EvaluationCase] = []
    for path in sorted(cases_root.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            EvaluationCase(
                case_id=raw.get("case_id", ""),
                title=raw.get("title", ""),
                requirement=raw.get("requirement", ""),
                repository_type=raw.get("repository_type", ""),
                expected_domains=tuple(raw.get("expected_domains", [])),
                expected_file_patterns=tuple(raw.get("expected_file_patterns", [])),
                expected_risks=tuple(raw.get("expected_risks", [])),
                expected_acceptance_topics=tuple(raw.get("expected_acceptance_topics", [])),
                forbidden_claims=tuple(raw.get("forbidden_claims", [])),
                human_review_notes=raw.get("human_review_notes", ""),
            )
        )
    return tuple(cases)


def run_mock_evaluation(
    cases: tuple[EvaluationCase, ...],
    repository_root: Path,
    output_root: Path,
) -> EvaluationReport:
    """Run contract checks through the existing mock-only CLI runner."""
    runs: list[EvaluationRun] = []
    for case in cases:
        case_output = output_root / case.case_id
        missing_files = [
            path for path in case.expected_file_patterns if not (repository_root / path).is_file()
        ]
        exit_code = (
            3
            if missing_files
            else run(
                repo=repository_root,
                requirement=case.requirement,
                output=case_output,
                provider="mock",
                max_files=8,
            )
        )
        run_dirs = sorted(case_output.glob("run-*"))
        findings = ()
        artifact_directory = case_output.as_posix()
        if missing_files:
            from specflow.evaluation.models import EvaluationFinding

            findings = (
                EvaluationFinding(
                    "case_file_missing", f"Expected files missing: {', '.join(missing_files)}."
                ),
            )
        elif exit_code == 0 and len(run_dirs) == 1:
            artifact_directory = run_dirs[0].as_posix()
            findings = validate_artifacts(run_dirs[0], repository_root, require_live=False)
        else:
            from specflow.evaluation.models import EvaluationFinding

            findings = (EvaluationFinding("mock_run_failed", f"Mock CLI exit code: {exit_code}."),)
        status = EvaluationStatus.PASSED if not findings else EvaluationStatus.FAILED
        runs.append(
            EvaluationRun(
                case_id=case.case_id,
                mode=EvaluationMode.MOCK_CONTRACT,
                status=status,
                artifact_directory=artifact_directory,
                findings=findings,
            )
        )
    status = (
        EvaluationStatus.PASSED
        if all(run.status == EvaluationStatus.PASSED for run in runs)
        else EvaluationStatus.FAILED
    )
    return EvaluationReport(
        mode=EvaluationMode.MOCK_CONTRACT,
        status=status,
        runs=tuple(runs),
        live_validation_status=EvaluationStatus.BLOCKED,
        notes=("blocked_live_validation: user must run the provider in an independent shell.",),
    )


def validate_live_artifact_import(
    artifact_directory: Path, repository_root: Path
) -> LiveValidationRecord:
    """Validate a user-created artifact directory without calling a provider."""
    findings = validate_artifacts(artifact_directory, repository_root, require_live=True)
    manifest_path = artifact_directory / "manifest.json"
    provider_type = ""
    model = ""
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            provider_type = str(manifest.get("provider_type", ""))
            model = str(manifest.get("model", ""))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    return LiveValidationRecord(
        status=EvaluationStatus.PASSED if not findings else EvaluationStatus.FAILED,
        artifact_directory=artifact_directory.as_posix(),
        provider_type=provider_type,
        model=model,
        findings=findings,
    )
