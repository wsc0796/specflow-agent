"""Pure, read-only validation for generated evaluation artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from specflow.evaluation.models import EvaluationFinding

REQUIRED_ARTIFACTS = frozenset(
    {
        "manifest.json",
        "analysis.json",
        "generation.json",
        "review.json",
        "sources.json",
        "tool-calls.json",
        "trace.json",
        "technical-spec.md",
        "test-plan.md",
        "run-summary.md",
    }
)
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SECRET = re.compile(
    r"(?:(?<!\w)api[_-]?key\s*[:=]|(?<!\w)authorization\s*[:=]|(?<!\w)bearer\s+[\w.-]+|(?<!\w)access[_-]?token\s*[:=]|(?<!\w)password\s*[:=]|(?<!\w)secret\s*[:=]|sk-[\w-]{12,})",
    re.I,
)
_TOOLS = frozenset({"list_files", "search_code", "read_file"})


def validate_artifacts(
    artifact_dir: Path, repository_root: Path, *, require_live: bool
) -> tuple[EvaluationFinding, ...]:
    findings: list[EvaluationFinding] = []
    if not artifact_dir.is_dir():
        return (EvaluationFinding("artifact_directory_missing", "Artifact directory is missing."),)
    missing = sorted(n for n in REQUIRED_ARTIFACTS if not _safe_file(artifact_dir, n))
    if missing:
        return (EvaluationFinding("artifact_missing", f"Missing artifacts: {', '.join(missing)}"),)
    payloads = {
        n: _read_json(artifact_dir, findings, n)
        for n in (
            "manifest.json",
            "sources.json",
            "trace.json",
            "tool-calls.json",
            "analysis.json",
            "generation.json",
            "review.json",
        )
    }
    if any(v is None for v in payloads.values()):
        return tuple(findings)
    manifest, sources, traces, calls, analysis, generation, review = (payloads[n] for n in payloads)
    _validate_manifest(manifest, findings, require_live)
    _validate_lineage(analysis, generation, review, findings)
    _validate_traces(traces, findings)
    if (
        not isinstance(calls, list)
        or not calls
        or any(not isinstance(c, dict) or c.get("tool_name") not in _TOOLS for c in calls)
    ):
        findings.append(
            EvaluationFinding("tool_calls_missing", "Expected read-only tool call records.")
        )
    _validate_sources(sources, repository_root, findings)
    for name in REQUIRED_ARTIFACTS:
        try:
            if _SECRET.search((artifact_dir / name).read_text(encoding="utf-8")):
                findings.append(
                    EvaluationFinding("secret_detected", f"Sensitive pattern in {name}.")
                )
        except (OSError, UnicodeDecodeError):
            findings.append(
                EvaluationFinding("artifact_unreadable", f"Unreadable artifact: {name}.")
            )
    return tuple(findings)


def _safe_file(root: Path, name: str) -> bool:
    path = root / name
    if not path.is_file() or path.is_symlink():
        return False
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _read_json(root: Path, findings: list[EvaluationFinding], name: str):
    try:
        return json.loads((root / name).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        findings.append(EvaluationFinding("invalid_json", f"Invalid JSON: {name}."))
        return None


def _validate_manifest(value: object, findings: list[EvaluationFinding], live: bool) -> None:
    if not isinstance(value, dict):
        findings.append(EvaluationFinding("manifest_invalid", "manifest.json must be an object."))
        return
    if live and value.get("provider_type") == "mock":
        findings.append(
            EvaluationFinding(
                "live_provider_mock", "Live validation rejects mock provider artifacts."
            )
        )
    if live and not str(value.get("model", "")).strip():
        findings.append(
            EvaluationFinding("live_model_missing", "Live validation requires a model.")
        )
    if value.get("status") not in {"completed", "failed"}:
        findings.append(
            EvaluationFinding("workflow_status_invalid", "Manifest workflow status is invalid.")
        )


def _validate_lineage(a: object, g: object, r: object, findings: list[EvaluationFinding]) -> None:
    if not all(isinstance(x, dict) for x in (a, g, r)):
        findings.append(EvaluationFinding("worker_output_invalid", "Worker JSON must be objects."))
        return
    hashes = (
        a.get("analysis_hash"),
        g.get("analysis_hash"),
        g.get("generation_hash"),
        r.get("analysis_hash"),
        r.get("generation_hash"),
    )
    if any(not isinstance(x, str) or not _HASH.fullmatch(x) for x in hashes):
        findings.append(
            EvaluationFinding("hash_missing", "Worker hash lineage must contain SHA-256 hashes.")
        )
        return
    if g["analysis_hash"] != a["analysis_hash"]:
        findings.append(
            EvaluationFinding(
                "analysis_lineage_invalid", "Generation does not reference analysis hash."
            )
        )
    if r["analysis_hash"] != a["analysis_hash"] or r["generation_hash"] != g["generation_hash"]:
        findings.append(
            EvaluationFinding("review_lineage_invalid", "Review hash lineage is invalid.")
        )


def _validate_traces(value: object, findings: list[EvaluationFinding]) -> None:
    roles = (
        {x.get("metadata", {}).get("worker_role") for x in value if isinstance(x, dict)}
        if isinstance(value, list)
        else set()
    )
    if roles != {"analyze", "generate", "review"}:
        findings.append(
            EvaluationFinding(
                "worker_trace_missing", "Expected Analyze, Generate, and Review traces."
            )
        )


def _validate_sources(value: object, root: Path, findings: list[EvaluationFinding]) -> None:
    if not isinstance(value, dict):
        findings.append(EvaluationFinding("sources_invalid", "sources.json must be an object."))
        return
    candidates = (
        list(value.get("selected_files", []))
        + list(value.get("matched_files", []))
        + [x.get("relative_path", "") for x in value.get("excerpts", []) if isinstance(x, dict)]
    )
    if not candidates:
        findings.append(
            EvaluationFinding("source_evidence_missing", "Expected repository source evidence.")
        )
    for item in sorted(set(map(str, candidates))):
        path = Path(item)
        if path.is_absolute() or ".." in path.parts:
            findings.append(
                EvaluationFinding("source_path_external", f"Invalid source path: {item}.")
            )
            continue
        resolved = (root / path).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            findings.append(
                EvaluationFinding("source_path_external", f"External source path: {item}.")
            )
            continue
        if not resolved.is_file():
            findings.append(
                EvaluationFinding("source_path_missing", f"Missing source path: {item}.")
            )
