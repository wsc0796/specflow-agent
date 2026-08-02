"""Read-only verifier for a live multi-agent artifact pack (Phase 4).

Checks the Phase 4 artifact contract without calling any provider:

- required artifact files exist and parse as JSON;
- ``task-briefs.json`` canonical hash recomputes;
- manifest terminal state, budget snapshot, and revision artifacts are present
  and consistent with ``metrics.json``;
- MODEL_CALL_* trace events are metadata-only and never contain prompts;
- evidence refs in task briefs resolve against the evidence index;
- no credential patterns in any artifact file.

Exit code 0 = PASS, 1 = FAILED (findings printed to stdout).
"""

from __future__ import annotations

import json
import re
import sys
from hashlib import sha256
from pathlib import Path

REQUIRED = (
    "metadata.json",
    "frozen-config.json",
    "task-briefs.json",
    "evidence-index.json",
    "execution-manifest.json",
    "trace.jsonl",
    "initial-agent-outputs.json",
    "review-findings.json",
    "revision-inputs.json",
    "revision-results.json",
    "finding-resolutions.json",
    "final-plan.md",
    "metrics.json",
    "rerun.md",
)

SECRET_RE = re.compile(
    r"(?:(?<!\w)api[_-]?key\s*[:=]|(?<!\w)authorization\s*[:=]|"
    r"(?<!\w)bearer\s+[\w.-]+|(?<!\w)access[_-]?token\s*[:=]|"
    r"(?<!\w)password\s*[:=]|(?<!\w)secret\s*[:=]|(?<!\w)sk-[\w-]{12,})",
    re.I,
)


def verify(artifact_dir: Path) -> list[str]:
    findings: list[str] = []
    if not artifact_dir.is_dir():
        return ["artifact_directory_missing"]

    missing = [name for name in REQUIRED if not (artifact_dir / name).is_file()]
    if missing:
        return [f"missing_artifacts: {', '.join(missing)}"]

    for name in REQUIRED:
        if name.endswith(".json") or name.endswith(".jsonl"):
            try:
                if name.endswith(".jsonl"):
                    for line in (artifact_dir / name).read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            json.loads(line)
                else:
                    _read(artifact_dir / name)
            except (OSError, ValueError) as exc:
                findings.append(f"{name}_unparseable: {type(exc).__name__}")
        if SECRET_RE.search((artifact_dir / name).read_text(encoding="utf-8", errors="replace")):
            findings.append(f"secret_detected_in_{name}")

    task_briefs = _read(artifact_dir / "task-briefs.json")
    manifest = _read(artifact_dir / "execution-manifest.json")
    metrics = _read(artifact_dir / "metrics.json")
    evidence_index = _read(artifact_dir / "evidence-index.json")

    if isinstance(task_briefs, dict) and isinstance(task_briefs.get("canonical_hash"), str):
        recomputed = _canonical_hash(
            {key: value for key, value in task_briefs.items() if key != "canonical_hash"}
        )
        if recomputed != task_briefs["canonical_hash"]:
            findings.append("task_briefs_canonical_hash_mismatch")
    else:
        findings.append("task_briefs_canonical_hash_missing")

    if not isinstance(manifest, dict):
        findings.append("manifest_not_object")
    else:
        state = manifest.get("workflow_state")
        if state not in {"completed", "completed_degraded", "needs_human_review"}:
            findings.append(f"unexpected_terminal_state: {state}")
        if not isinstance(manifest.get("budget_snapshot"), dict):
            findings.append("budget_snapshot_missing")
        if "revision_artifacts" not in manifest and "revision" not in manifest:
            findings.append("revision_evidence_missing")

    if not isinstance(metrics, dict) or not isinstance(metrics.get("budget_snapshot"), dict):
        findings.append("metrics_budget_snapshot_missing")
    elif manifest.get("budget_snapshot", {}).get("snapshot_id") != metrics.get(
        "budget_snapshot", {}
    ).get("snapshot_id"):
        # Snapshots are captured at slightly different times; compare core facts.
        manifest_calls = manifest.get("budget_snapshot", {}).get("provider_calls", {})
        metrics_calls = metrics.get("budget_snapshot", {}).get("provider_calls", {})
        if manifest_calls.get("attempts") != metrics_calls.get("attempts"):
            findings.append("budget_snapshot_inconsistent")

    mode = manifest.get("budget_snapshot", {}).get("execution_mode")
    if mode == "live":
        attempts = manifest.get("budget_snapshot", {}).get("provider_calls", {}).get("attempts", 0)
        if attempts <= 0:
            findings.append("live_run_without_provider_attempts")
        tokens = manifest.get("budget_snapshot", {}).get("tokens", {})
        if tokens.get("usage_known") is False and tokens.get("unknown_calls", 0) <= 0:
            findings.append("token_usage_status_not_recorded")

    if isinstance(evidence_index, dict):
        known_evidence = set(evidence_index.get("evidence", {}).keys()) | set(
            reference.get("evidence_id", "") for reference in evidence_index.get("references", [])
        )
        if isinstance(task_briefs, dict):
            for brief in task_briefs.get("briefs", []):
                for ref in brief.get("evidence_refs", []):
                    if isinstance(ref, dict) and ref.get("evidence_id") not in known_evidence:
                        findings.append(f"unknown_evidence_ref: {ref.get('evidence_id')}")

    trace_lines = (artifact_dir / "trace.jsonl").read_text(encoding="utf-8")
    if "PROMPT_SECRET" in trace_lines or '"content":' in trace_lines:
        findings.append("trace_may_contain_prompt_content")
    for event in trace_lines.splitlines():
        try:
            payload = json.loads(event)
        except ValueError:
            findings.append("trace_line_unparseable")
            continue
        if payload.get("event_type", "").startswith("MODEL_CALL_") and "snapshot_id" not in payload:
            findings.append("model_call_event_missing_snapshot_reference")

    return sorted(set(findings))


def _read(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(raw).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_live_multi_agent.py <artifact-directory>")
        return 2
    findings = verify(Path(sys.argv[1]))
    if findings:
        for finding in findings:
            print(f"FAILED: {finding}")
        return 1
    print("PASS: live multi-agent artifact pack verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
